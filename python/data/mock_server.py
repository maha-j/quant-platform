"""Serveur OHLCV de référence (FastAPI) pour dev, démo et tests d'intégration.

Expose ``GET /ohlcv?symbol=&timeframe=&limit=`` au schéma attendu par
:class:`OhlcvHttpClient`. Génère des barres synthétiques déterministes (seed
dérivée du symbole) — aucun accès réseau, idéal pour valider le chemin REST
de bout en bout sans provider externe.
"""
from __future__ import annotations

import math
import random

from fastapi import FastAPI


def _synthetic_bars(symbol: str, limit: int) -> list[dict]:
    """Barres OHLCV déterministes par seed, mais au bruit réellement aléatoire.

    Le drift suit un régime lent (structure faible, apprenable) tandis que le
    bruit provient d'un PRNG seedé : imprévisible à partir des features → des
    métriques *réalistes* (proches du hasard), pas un sur-apprentissage factice.
    """

    seed = sum(ord(c) for c in symbol)
    rng = random.Random(seed)
    bars: list[dict] = []
    price = 100.0 + seed % 50
    t0 = 1_600_000_000_000  # epoch ms de départ
    step_ms = 900_000       # 15 minutes
    for i in range(limit):
        drift = 0.0003 * math.sin(i / 40.0 + seed)
        noise = rng.gauss(0.0, 0.004)
        price *= 1 + drift + noise
        high = price * (1 + abs(noise) + 0.0005)
        low = price * (1 - abs(noise) - 0.0005)
        bars.append({
            "t": t0 + i * step_ms,
            "o": round(price * (1 - noise / 2), 5),
            "h": round(high, 5),
            "l": round(low, 5),
            "c": round(price, 5),
            "v": round(1000 + abs(noise) * 1e5, 2),
        })
    return bars


def create_mock_app() -> FastAPI:
    """Fabrique l'application FastAPI du provider mock."""

    app = FastAPI(title="Mock OHLCV Provider", version="0.1.0")

    @app.get("/ohlcv")
    def ohlcv(symbol: str, timeframe: str = "M15", limit: int = 500) -> list[dict]:
        return _synthetic_bars(symbol, min(limit, 10_000))

    return app


app = create_mock_app()
