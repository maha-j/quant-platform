"""Providers concrets implémentant :class:`DataSource`.

- :class:`RestDataSource`        : API REST JSON (cross-plateforme, via httpx).
- :class:`MetaTrader5DataSource` : terminal MT5 (module dédié ``data.mt5``).

Tous retournent un ``pandas.DataFrame`` indexé par le temps (contrat commun),
et restent interchangeables avec :class:`CsvDataSource` (LSP).
"""
from __future__ import annotations

import pandas as pd

from .fetcher import DataSource
from .http_client import Bar, OhlcvHttpClient
from .mt5 import MetaTrader5DataSource  # ré-export (compat imports)

__all__ = ["bars_to_frame", "RestDataSource", "MetaTrader5DataSource"]


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
