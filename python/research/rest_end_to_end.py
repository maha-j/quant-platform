"""Démo bout-en-bout à partir d'un **provider REST réel** (pas de données synthétiques inline).

Chaîne : RestDataSource/OhlcvHttpClient -> barres -> features NumPy -> training
walk-forward -> signaux -> backtest. Le provider est le serveur FastAPI
`data.mock_server`, appelé **en ASGI in-process** (httpx ASGITransport) : le
chemin HTTP complet (params, JSON, parsing) est exercé sans réseau ni pandas.

Pour viser un vrai broker, remplacer le transport ASGI par un
``httpx.AsyncClient(base_url="https://mon-vendor")`` — le reste est identique.
"""
from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

import httpx
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "python"))

from backtests.engine.metrics import build_report  # noqa: E402
from data.http_client import Bar, OhlcvHttpClient  # noqa: E402
from data.mock_server import create_mock_app  # noqa: E402
from ml.models.predictors import logistic_factory  # noqa: E402
from ml.models.registry import ModelRegistry  # noqa: E402
from ml.training.pipeline import train_and_validate  # noqa: E402
from research.ml_end_to_end import (  # noqa: E402
    backtest_from_probabilities, numpy_features)


def bars_to_arrays(bars: list[Bar]) -> dict[str, np.ndarray]:
    """Convertit une liste de :class:`Bar` en tableaux NumPy (sans pandas)."""

    return {
        "close": np.array([b.close for b in bars], dtype=float),
        "high": np.array([b.high for b in bars], dtype=float),
        "low": np.array([b.low for b in bars], dtype=float),
    }


async def fetch_bars(symbol: str, timeframe: str, limit: int) -> list[Bar]:
    """Récupère les barres via le chemin REST complet (ASGI in-process)."""

    transport = httpx.ASGITransport(app=create_mock_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://mock") as http:
        client = OhlcvHttpClient("http://mock", client=http)
        return await client.fetch(symbol, timeframe, limit)


def main() -> None:
    bars_list = asyncio.run(fetch_bars("EURUSD", "M15", 3000))
    print(f"provider REST: {len(bars_list)} barres reçues")

    bars = bars_to_arrays(bars_list)
    x, y = numpy_features(bars)
    print(f"dataset: {x.shape[0]} échantillons, {x.shape[1]} features")

    with tempfile.TemporaryDirectory() as tmp:
        registry = ModelRegistry(Path(tmp))
        result = train_and_validate(
            features=x, target=y, factory=logistic_factory, registry=registry,
            algo="logistic", feature_version="v1",
            hyperparameters={"lr": 0.1, "epochs": 500}, n_folds=5, embargo=10,
        )
        print("validation walk-forward:", json.dumps(result, indent=2))

        model = logistic_factory(x, y)
        equity = backtest_from_probabilities(bars, model.predict(x))
        print("backtest:", json.dumps(build_report(equity).to_dict(), indent=2))


if __name__ == "__main__":
    main()
