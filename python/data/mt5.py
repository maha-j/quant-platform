"""Provider de données MetaTrader 5.

Implémente :class:`DataSource` au-dessus du package ``MetaTrader5`` (terminal MT5,
Windows). Le package natif est importé **paresseusement** et le client MT5 est
**injectable** : la plateforme reste importable sur des hôtes sans MT5 (Linux/CI),
et le provider est testable via un faux client (aucun terminal requis).

Points clés :
- connexion gérée (``connect``/``close`` + context manager),
- sélection du symbole dans le Market Watch avant lecture,
- mapping des timeframes MT5,
- appels bloquants MT5 déportés hors de la boucle asyncio (``asyncio.to_thread``),
- gestion d'erreurs explicite via ``last_error()``.
"""
from __future__ import annotations

import asyncio
from typing import Any, Protocol

import pandas as pd

from common.config import MetaTrader5Config

from .fetcher import DataSource


class MT5Client(Protocol):
    """Sous-ensemble du package ``MetaTrader5`` utilisé ici (facilite l'injection)."""

    def initialize(self, *args: Any, **kwargs: Any) -> bool: ...
    def login(self, *args: Any, **kwargs: Any) -> bool: ...
    def symbol_select(self, symbol: str, enable: bool) -> bool: ...
    def copy_rates_from_pos(self, symbol: str, timeframe: int, start: int,
                            count: int) -> Any: ...
    def last_error(self) -> Any: ...
    def shutdown(self) -> None: ...


def _load_mt5() -> MT5Client:
    """Importe le vrai package MetaTrader5 (paresseux ; Windows uniquement)."""

    import MetaTrader5 as mt5  # noqa: N813

    return mt5


def _rates_to_frame(rates: Any) -> pd.DataFrame:
    """Convertit le tableau de barres MT5 en DataFrame OHLCV indexé par le temps."""

    frame = pd.DataFrame(rates)
    if frame.empty:
        return frame
    frame["time"] = pd.to_datetime(frame["time"], unit="s")
    frame = frame.set_index("time").sort_index()
    if "tick_volume" in frame.columns:
        frame = frame.rename(columns={"tick_volume": "volume"})
    return frame


class MetaTrader5DataSource(DataSource):
    """Source de barres OHLCV issue d'un terminal MetaTrader 5."""

    _TF = {
        "M1": "TIMEFRAME_M1", "M5": "TIMEFRAME_M5", "M15": "TIMEFRAME_M15",
        "M30": "TIMEFRAME_M30", "H1": "TIMEFRAME_H1", "H4": "TIMEFRAME_H4",
        "D1": "TIMEFRAME_D1", "W1": "TIMEFRAME_W1",
    }

    def __init__(self, client: MT5Client, config: MetaTrader5Config) -> None:
        self._mt5 = client
        self._config = config

    @classmethod
    def connect(cls, config: MetaTrader5Config,
                client: MT5Client | None = None) -> "MetaTrader5DataSource":
        """Établit la connexion au terminal et retourne un provider prêt.

        Args:
            config: identifiants/paramètres (voir :class:`MetaTrader5Config`).
            client: client MT5 injecté (tests) ; sinon le package réel est chargé.
        """

        mt5 = client or _load_mt5()
        kwargs: dict[str, Any] = {"timeout": config.timeout_ms}
        if config.path:
            kwargs["path"] = config.path
        if config.login is not None:
            kwargs.update(login=config.login, password=config.password,
                          server=config.server)
        if not mt5.initialize(**kwargs):
            raise ConnectionError(f"MT5 initialize a échoué: {mt5.last_error()}")
        return cls(mt5, config)

    def _timeframe(self, timeframe: str) -> int:
        try:
            return getattr(self._mt5, self._TF[timeframe])
        except KeyError as exc:
            raise ValueError(f"timeframe non supporté: {timeframe}") from exc

    def _fetch_sync(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        """Lecture bloquante (exécutée dans un thread par :meth:`fetch`)."""

        if not self._mt5.symbol_select(symbol, True):
            raise RuntimeError(
                f"symbol_select a échoué pour {symbol}: {self._mt5.last_error()}")
        rates = self._mt5.copy_rates_from_pos(
            symbol, self._timeframe(timeframe), 0, limit)
        if rates is None or len(rates) == 0:
            raise RuntimeError(
                f"copy_rates vide pour {symbol}: {self._mt5.last_error()}")
        return _rates_to_frame(rates)

    async def fetch(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        """Récupère ``limit`` dernières barres sans bloquer la boucle événementielle."""

        return await asyncio.to_thread(self._fetch_sync, symbol, timeframe, limit)

    def close(self) -> None:
        self._mt5.shutdown()

    def __enter__(self) -> "MetaTrader5DataSource":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
