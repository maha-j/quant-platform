"""Side-car ZeroMQ → TCP pour l'EA MQL5.

MQL5 sait ouvrir un socket **TCP** natif (`SocketConnect`) mais pas parler
ZeroMQ. Ce side-car s'abonne au flux ZeroMQ PUB des signaux et le relaie, ligne
JSON par ligne, à tout terminal MT5 connecté en TCP — sans DLL côté MT5.

Topologie :

    SignalPublisher (PUB) ──► [ce side-car : SUB + serveur TCP] ──► EA (SocketConnect)

Lancer : ``python -m execution.zmq_tcp_bridge``
Robustesse : abonnement non bloquant, tolérance aux clients lents, un thread
d'acceptation par connexion terminal.
"""
from __future__ import annotations

import asyncio
import json

from common.config import Settings, load_settings
from common.logging import configure_logging, get_logger

try:
    import zmq
    import zmq.asyncio

    _ZMQ = True
except ImportError:  # pragma: no cover
    _ZMQ = False

log = get_logger("zmq_tcp_bridge")


class ZmqTcpBridge:
    """Relaie les signaux ZeroMQ PUB vers des clients TCP (EA MQL5)."""

    def __init__(self, settings: Settings, tcp_host: str = "0.0.0.0",
                 tcp_port: int = 5560) -> None:
        if not _ZMQ:
            raise RuntimeError("pyzmq requis pour le side-car")
        self._settings = settings
        self._host, self._port = tcp_host, tcp_port
        self._clients: set[asyncio.StreamWriter] = set()

    async def _handle_client(self, _reader: asyncio.StreamReader,
                             writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        self._clients.add(writer)
        log.info("client_connecté", peer=str(peer))
        try:
            await writer.wait_closed()
        finally:
            self._clients.discard(writer)
            log.info("client_déconnecté", peer=str(peer))

    async def _pump_signals(self) -> None:
        ctx = zmq.asyncio.Context.instance()
        sub = ctx.socket(zmq.SUB)
        sub.connect(self._settings.messaging.signals_endpoint)
        sub.setsockopt(zmq.SUBSCRIBE, b"signals")
        log.info("abonné", endpoint=self._settings.messaging.signals_endpoint)
        while True:
            _topic, payload = await sub.recv_multipart()
            # On aplatit l'enveloppe en un objet JSON attendu par SignalReceiver.mqh.
            env = json.loads(payload.decode())
            flat = {**env.get("signal", {}), "signal_id": env.get("signal_id"),
                    "issued_at": int(env.get("issued_at", 0))}
            line = (json.dumps(flat, separators=(",", ":")) + "\n").encode()
            await self._broadcast(line)

    async def _broadcast(self, line: bytes) -> None:
        for writer in list(self._clients):
            try:
                writer.write(line)
                await writer.drain()
            except (ConnectionError, RuntimeError):
                self._clients.discard(writer)

    async def run(self) -> None:
        server = await asyncio.start_server(self._handle_client, self._host, self._port)
        log.info("tcp_écoute", host=self._host, port=self._port)
        async with server:
            await asyncio.gather(server.serve_forever(), self._pump_signals())


def main() -> None:
    configure_logging(json=False)
    asyncio.run(ZmqTcpBridge(load_settings()).run())


if __name__ == "__main__":
    main()
