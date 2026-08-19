"""Implémentations concrètes de :class:`Predictor`.

- :class:`LogisticPredictor` : régression logistique en NumPy pur — toujours
  disponible, sert de baseline et garantit un pipeline exécutable partout.
- :func:`lightgbm_factory` / :func:`sklearn_factory` : fabriques optionnelles
  (importées paresseusement) pour les modèles de production.

Toutes respectent l'interface :class:`Predictor` (LSP) : ``predict`` renvoie une
probabilité dans [0, 1]. Le pipeline reste agnostique du modèle.
"""
from __future__ import annotations

import numpy as np

from ml.models.registry import Predictor


class LogisticPredictor(Predictor):
    """Régression logistique entraînée par descente de gradient (NumPy)."""

    def __init__(self, weights: np.ndarray, bias: float, mean: np.ndarray,
                 std: np.ndarray) -> None:
        self._w, self._b, self._mean, self._std = weights, bias, mean, std

    @staticmethod
    def _sigmoid(z: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))

    @classmethod
    def fit(cls, x: np.ndarray, y: np.ndarray, lr: float = 0.1,
            epochs: int = 500, l2: float = 1e-3) -> "LogisticPredictor":
        """Entraîne le modèle (features standardisées, régularisation L2)."""

        mean, std = x.mean(0), x.std(0) + 1e-9
        xs = (x - mean) / std
        n, d = xs.shape
        w, b = np.zeros(d), 0.0
        for _ in range(epochs):
            p = cls._sigmoid(xs @ w + b)
            grad_w = xs.T @ (p - y) / n + l2 * w
            grad_b = float(np.mean(p - y))
            w -= lr * grad_w
            b -= lr * grad_b
        return cls(w, b, mean, std)

    def predict(self, features: np.ndarray) -> np.ndarray:
        xs = (features - self._mean) / self._std
        return self._sigmoid(xs @ self._w + self._b)


def logistic_factory(x: np.ndarray, y: np.ndarray) -> Predictor:
    """Fabrique baseline (toujours disponible)."""

    return LogisticPredictor.fit(x, y)


def lightgbm_factory(x: np.ndarray, y: np.ndarray) -> Predictor:  # pragma: no cover
    """Fabrique LightGBM (production) — nécessite ``lightgbm`` installé."""

    import lightgbm as lgb

    model = lgb.LGBMClassifier(n_estimators=200, num_leaves=31, learning_rate=0.05)
    model.fit(x, y)

    class _LgbPredictor(Predictor):
        def predict(self, features: np.ndarray) -> np.ndarray:
            return model.predict_proba(features)[:, 1]

    return _LgbPredictor()


def sklearn_factory(x: np.ndarray, y: np.ndarray) -> Predictor:  # pragma: no cover
    """Fabrique gradient boosting scikit-learn (production)."""

    from sklearn.ensemble import GradientBoostingClassifier

    model = GradientBoostingClassifier()
    model.fit(x, y)

    class _SkPredictor(Predictor):
        def predict(self, features: np.ndarray) -> np.ndarray:
            return model.predict_proba(features)[:, 1]

    return _SkPredictor()
