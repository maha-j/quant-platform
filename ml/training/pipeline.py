"""Pipeline d'entraînement de bout en bout.

Orchestre : dataset -> split walk-forward purgé -> entraînement -> validation ->
versionning. Le choix du modèle est injecté (factory), respectant l'interface
:class:`Predictor` — remplacer LightGBM par un Transformer ne change pas le
pipeline.
"""
from __future__ import annotations

from collections.abc import Callable

import numpy as np

from ml.models.registry import ModelRegistry, Predictor, compute_data_hash

# Fabrique de modèle : (X_train, y_train) -> Predictor entraîné.
ModelFactory = Callable[[np.ndarray, np.ndarray], Predictor]


def _accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Exactitude (numpy pur — pas de dépendance externe)."""

    return float(np.mean(y_true == y_pred)) if y_true.size else 0.0


def _roc_auc(y_true: np.ndarray, scores: np.ndarray) -> float:
    """AUC via la statistique de Mann-Whitney (rang moyen des positifs)."""

    pos = scores[y_true == 1]
    neg = scores[y_true == 0]
    if pos.size == 0 or neg.size == 0:
        return 0.5
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, scores.size + 1)
    rank_pos = ranks[y_true == 1].sum()
    auc = (rank_pos - pos.size * (pos.size + 1) / 2) / (pos.size * neg.size)
    return float(auc)


def purged_splits(n: int, n_folds: int, embargo: int) -> list[tuple[slice, slice]]:
    """Découpe walk-forward purgée + embargo (anti-fuite temporelle)."""

    fold = n // (n_folds + 1)
    splits: list[tuple[slice, slice]] = []
    for i in range(1, n_folds + 1):
        train_end = fold * i
        test_start = train_end + embargo
        test_end = min(test_start + fold, n)
        if test_start >= n:
            break
        splits.append((slice(0, train_end), slice(test_start, test_end)))
    return splits


def train_and_validate(features: np.ndarray, target: np.ndarray,
                       factory: ModelFactory, registry: ModelRegistry,
                       algo: str, feature_version: str, hyperparameters: dict,
                       n_folds: int = 5, embargo: int = 10) -> dict:
    """Entraîne et valide en walk-forward, puis versionne le résultat.

    La métrique de validation est agrégée sur les folds *out-of-sample*.
    """

    accs, aucs = [], []
    for train_idx, test_idx in purged_splits(len(features), n_folds, embargo):
        model = factory(features[train_idx], target[train_idx])
        proba = model.predict(features[test_idx])
        preds = (proba >= 0.5).astype(int)
        accs.append(_accuracy(target[test_idx], preds))
        if len(np.unique(target[test_idx])) > 1:
            aucs.append(_roc_auc(target[test_idx], proba))

    metrics = {
        "accuracy_oos": float(np.mean(accs)) if accs else 0.0,
        "auc_oos": float(np.mean(aucs)) if aucs else 0.0,
        "folds": len(accs),
    }
    card = registry.register(
        algo=algo,
        data_hash=compute_data_hash(features, target),
        feature_version=feature_version,
        hyperparameters=hyperparameters,
        metrics=metrics,
    )
    return {"model_id": card.model_id, "metrics": metrics}
