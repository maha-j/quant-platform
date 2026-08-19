"""Récupération asynchrone des données de marché.

Interface :class:`DataSource` (DIP) : le reste du système dépend de cette
abstraction, pas d'un provider concret. Implémentations interchangeables
(CSV local, broker, base). ``asyncio`` permet de récupérer plusieurs symboles
en parallèle sans bloquer.
"""
from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd
import polars as pl


class DataSource(ABC):
    """Contrat d'une source de barres OHLCV."""

    @abstractmethod
    async def fetch(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        """Retourne un DataFrame indexé par temps, colonnes OHLCV."""


class CsvDataSource(DataSource):
    """Source fichier (recherche/backtest). Lecture rapide via Polars."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    async def fetch(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        path = self._root / f"{symbol}_{timeframe}.csv"
        # Lecture I/O déportée hors de la boucle événementielle.
        frame = await asyncio.to_thread(
            lambda: pl.read_csv(path).tail(limit).to_pandas()
        )
        return frame.set_index("time")


class MarketDataService:
    """Façade de récupération multi-symboles concurrente."""

    def __init__(self, source: DataSource) -> None:
        self._source = source

    async def fetch_many(self, symbols: list[str], timeframe: str,
                         limit: int) -> dict[str, pd.DataFrame]:
        """Récupère tous les symboles en parallèle."""

        results = await asyncio.gather(
            *(self._source.fetch(s, timeframe, limit) for s in symbols)
        )
        return dict(zip(symbols, results))
