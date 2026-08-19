"""Providers concrets implémentant :class:`DataSource`.

- :class:`RestDataSource`        : API REST JSON (cross-plateforme, via httpx).
- :class:`MetaTrader5DataSource` : terminal MT5 (import paresseux ; Windows/MT5).

Tous retournent un ``pandas.DataFrame`` indexé par le temps (contrat commun),
et restent interchangeables avec :class:`CsvDataSource` (LSP).
"""
from __future__ import annotations

import pandas as pd

from .fetcher import DataSource
from .http_client import Bar, OhlcvHttpClient


def bars_to_frame(bars: list[Bar]) -> pd.DataFrame:
    """Convertit des :class:`Bar` en DataFrame OHLCV indexé par le temps."""

    frame = pd.DataFrame([b.__dict__ for b in bars])
    if frame.empty:
        return frame
    frame["time"] = pd.to_datetime(frame["time"], unit="ms", errors="coerce")
    return frame.set_index("time").sort_index()


class RestDataSource(DataSource):
    """Source REST générique (broker/data-vendor exposant du JSON OHLCV)."""

    def __init__(self, base_url: str, path: str = "/ohlcv") -> None:
        self._client = OhlcvHttpClient(base_url, path)

    async def fetch(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        bars = await self._client.fetch(symbol, timeframe, limit)
        return bars_to_frame(bars)


class MetaTrader5DataSource(DataSource):
    """Source MetaTrader 5 (package ``MetaTrader5``, Windows/terminal MT5).

    Import paresseux : le module n'est chargé qu'à l'appel, la plateforme reste
    importable sur des hôtes sans MT5 (Linux/CI).
    """

    _TF = {
        "M1": "TIMEFRAME_M1", "M5": "TIMEFRAME_M5", "M15": "TIMEFRAME_M15",
        "M30": "TIMEFRAME_M30", "H1": "TIMEFRAME_H1", "H4": "TIMEFRAME_H4",
        "D1": "TIMEFRAME_D1",
    }

    def __init__(self) -> None:
        import MetaTrader5 as mt5  # noqa: N813  (import paresseux)

        if not mt5.initialize():
            raise RuntimeError(f"MT5 initialize a échoué: {mt5.last_error()}")
        self._mt5 = mt5

    async def fetch(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        mt5 = self._mt5
        tf = getattr(mt5, self._TF[timeframe])
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, limit)
        if rates is None:
            raise RuntimeError(f"copy_rates a échoué pour {symbol}: {mt5.last_error()}")
        frame = pd.DataFrame(rates)
        frame["time"] = pd.to_datetime(frame["time"], unit="s")
        return frame.set_index("time").rename(columns={"tick_volume": "volume"})

    def close(self) -> None:
        self._mt5.shutdown()
