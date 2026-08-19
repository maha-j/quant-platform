"""Démo bout-en-bout : dataset -> features -> training -> signal -> backtest.

Prototype de recherche *exécutable avec NumPy seul* (les features y sont
recalculées en NumPy pour l'autonomie ; la version de production passe par
`ml/features/engineering.py` sur pandas et les fabriques LightGBM/XGBoost).

Chaîne démontrée :
1. génération de barres OHLCV synthétiques (marche aléatoire + drift),
2. feature engineering sans fuite de futur,
3. entraînement + validation walk-forward purgée (pipeline agnostique du modèle),
4. versionning du modèle (registry),
5. génération de signaux et backtest avec rapport de performance exportable.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))            # ml.*, backtests.*
sys.path.insert(0, str(ROOT / "python"))  # common.*, strategies.*

from backtests.engine.metrics import build_report  # noqa: E402
from ml.models.predictors import logistic_factory  # noqa: E402
from ml.models.registry import ModelRegistry  # noqa: E402
from ml.training.pipeline import train_and_validate  # noqa: E402


def synthetic_ohlcv(n: int = 3000, seed: int = 7) -> dict[str, np.ndarray]:
    """Barres OHLCV synthétiques avec un léger signal exploitable."""

    rng = np.random.default_rng(seed)
    # Drift dépendant d'un régime lent -> il existe une structure à apprendre.
    regime = np.sin(np.linspace(0, 12 * np.pi, n)) * 0.0003
    steps = rng.normal(regime, 0.004, n)
    close = 100 * np.cumprod(1 + steps)
    high = close * (1 + np.abs(rng.normal(0, 0.002, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.002, n)))
    return {"close": close, "high": high, "low": low}


def numpy_features(bars: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    """Features + cible en NumPy pur (aucune fuite de futur)."""

    close = bars["close"]
    ret1 = np.diff(close, prepend=close[0]) / close
    ret5 = np.zeros_like(close)
    ret5[5:] = close[5:] / close[:-5] - 1

    def ema(x: np.ndarray, span: int) -> np.ndarray:
        a = 2 / (span + 1)
        out = np.empty_like(x)
        out[0] = x[0]
        for i in range(1, len(x)):
            out[i] = a * x[i] + (1 - a) * out[i - 1]
        return out

    ema_ratio = ema(close, 12) / ema(close, 26) - 1
    vol = np.array([ret1[max(0, i - 20):i + 1].std() for i in range(len(close))])

    feats = np.column_stack([ret1, ret5, ema_ratio, vol])
    target = (np.roll(close, -1) > close).astype(int)  # hausse au prochain pas
    # On retire la dernière ligne (cible non observable) et le warmup.
    return feats[30:-1], target[30:-1]


def backtest_from_probabilities(bars: dict[str, np.ndarray], proba: np.ndarray,
                                threshold: float = 0.52) -> np.ndarray:
    """Construit une courbe d'equity à partir des probabilités du modèle.

    Position longue si p>seuil, courte si p<1-seuil, plate sinon. Le rendement
    du pas suivant est appliqué à la position (décalage -> pas de look-ahead).
    """

    close = bars["close"][30:-1]
    fwd_ret = np.roll(close, -1) / close - 1
    fwd_ret[-1] = 0.0
    position = np.where(proba > threshold, 1.0, np.where(proba < 1 - threshold, -1.0, 0.0))
    strat_ret = position * fwd_ret
    return np.concatenate([[1.0], np.cumprod(1 + strat_ret)])


def main() -> None:
    bars = synthetic_ohlcv()
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

        # Modèle final entraîné sur tout l'historique -> signaux -> backtest.
        model = logistic_factory(x, y)
        proba = model.predict(x)
        equity = backtest_from_probabilities(bars, proba)
        report = build_report(equity)
        print("backtest:", json.dumps(report.to_dict(), indent=2))


if __name__ == "__main__":
    main()
