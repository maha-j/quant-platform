"""Pont temps réel Python → MQL5 via ZeroMQ.

Profil VPS (voir docs/architecture/communication.md) :
- :class:`SignalPublisher` publie les enveloppes signées sur un socket **PUB**
  (topic ``signals``). N terminaux/consommateurs s'abonnent sans couplage.
- :class:`TelemetryCollector` reçoit ordres/fills sur un socket **PULL**.

ZeroMQ gère la reconnexion et le fan-out ; MQL5 ne parlant pas ZeroMQ nativement,
un side-car (:mod:`execution.zmq_tcp_bridge`) traduit PUB→TCP pour l'EA.
"""
from __future__ import annotations

from common.config import Settings
from execution.service import SignalEnvelope
from strategies.signals import Signal

try:  # pyzmq optionnel en dev
    import zmq

    _ZMQ = True
except ImportError:  # pragma: no cover
    _ZMQ = False

SIGNAL_TOPIC = b"signals"


class SignalPublisher:
    """Publie des signaux signés sur un socket ZeroMQ PUB."""

    def __init__(self, settings: Settings) -> None:
        if not _ZMQ:
            raise RuntimeError("pyzmq requis pour SignalPublisher")
        self._settings = settings
        self._ctx = zmq.Context.instance()
        self._sock = self._ctx.socket(zmq.PUB)
        self._sock.bind(settings.messaging.signals_endpoint)

    def publish(self, signal: Signal) -> SignalEnvelope:
        """Signe puis diffuse le signal (topic + payload JSON)."""

        envelope = SignalEnvelope.wrap(signal, self._settings)
        self._sock.send_multipart(
            [SIGNAL_TOPIC, envelope.model_dump_json().encode()]
        )
        return envelope

    def close(self) -> None:
        self._sock.close(linger=0)


class TelemetryCollector:
    """Reçoit la télémétrie d'exécution (ordres, fills) sur un socket PULL."""

    def __init__(self, settings: Settings) -> None:
        if not _ZMQ:
            raise RuntimeError("pyzmq requis pour TelemetryCollector")
        self._ctx = zmq.Context.instance()
        self._sock = self._ctx.socket(zmq.PULL)
        self._sock.bind(settings.messaging.telemetry_endpoint)

    def poll(self, timeout_ms: int = 100) -> str | None:
        """Retourne le prochain message de télémétrie, ou ``None``."""

        if self._sock.poll(timeout_ms):
            return self._sock.recv_string()
        return None

    def close(self) -> None:
        self._sock.close(linger=0)
