"""Client HTTP OHLCV — transport + parsing, indépendant de pandas.

Séparé des providers (SRP) : cette couche ne fait que parler HTTP et normaliser
la réponse en :class:`Bar`. L'assemblage en ``pandas.DataFrame`` (contrat
:class:`DataSource`) vit dans ``providers.py``. Sans dépendance pandas, cette
couche est testable en isolation (httpx ``MockTransport``).

Deux schémas de réponse sont acceptés :
- objets  : ``[{"t":..,"o":..,"h":..,"l":..,"c":..,"v":..}, ...]``
- tableaux (style klines Binance) : ``[[t,o,h,l,c,v], ...]``
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class Bar:
    """Barre OHLCV normalisée (temps en epoch ms ou s selon la source)."""

    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


def parse_bars(payload: Sequence) -> list[Bar]:
    """Normalise une réponse JSON hétérogène en liste de :class:`Bar`."""

    bars: list[Bar] = []
    for row in payload:
        if isinstance(row, dict):
            bars.append(Bar(
                time=int(row.get("t", row.get("time", 0))),
                open=float(row.get("o", row.get("open"))),
                high=float(row.get("h", row.get("high"))),
                low=float(row.get("l", row.get("low"))),
                close=float(row.get("c", row.get("close"))),
                volume=float(row.get("v", row.get("volume", 0.0))),
            ))
        else:  # séquence positionnelle [t, o, h, l, c, v]
            bars.append(Bar(int(row[0]), float(row[1]), float(row[2]),
                            float(row[3]), float(row[4]),
                            float(row[5]) if len(row) > 5 else 0.0))
    return bars


class OhlcvHttpClient:
    """Récupère des barres OHLCV depuis une API REST JSON.

    Le client httpx est injectable (DIP) pour permettre les tests hors réseau.
    """

    def __init__(self, base_url: str, path: str = "/ohlcv",
                 client: httpx.AsyncClient | None = None) -> None:
        self._base = base_url.rstrip("/")
        self._path = path
        self._client = client or httpx.AsyncClient(base_url=self._base, timeout=10.0)

    async def fetch(self, symbol: str, timeframe: str, limit: int) -> list[Bar]:
        """Appelle l'API et retourne les barres normalisées."""

        resp = await self._client.get(
            self._path,
            params={"symbol": symbol, "timeframe": timeframe, "limit": limit},
        )
        resp.raise_for_status()
        return parse_bars(resp.json())

    async def aclose(self) -> None:
        await self._client.aclose()
