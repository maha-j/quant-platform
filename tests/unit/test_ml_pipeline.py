"""Tests du pipeline ML : prédicteur baseline + validation walk-forward."""
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "python"))

from ml.models.predictors import LogisticPredictor, logistic_factory  # noqa: E402
from ml.models.registry import ModelRegistry  # noqa: E402
from ml.training.pipeline import _roc_auc, purged_splits, train_and_validate  # noqa: E402


def _separable_dataset(n=400, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, 3))
    y = (x[:, 0] + 0.5 * x[:, 1] > 0).astype(int)  # frontière apprenable
    return x, y


def test_logistic_predictor_learns_separable():
    x, y = _separable_dataset()
    model = LogisticPredictor.fit(x, y)
    acc = ((model.predict(x) >= 0.5).astype(int) == y).mean()
    assert acc > 0.9


def test_purged_splits_no_overlap():
    splits = purged_splits(n=100, n_folds=4, embargo=5)
    for train, test in splits:
        assert train.stop + 5 <= test.start  # embargo respecté


def test_roc_auc_perfect_separation():
    y = np.array([0, 0, 1, 1])
    scores = np.array([0.1, 0.2, 0.8, 0.9])
    assert _roc_auc(y, scores) == 1.0


def test_train_and_validate_registers_model():
    x, y = _separable_dataset()
    with tempfile.TemporaryDirectory() as tmp:
        registry = ModelRegistry(Path(tmp))
        result = train_and_validate(
            x, y, factory=logistic_factory, registry=registry,
            algo="logistic", feature_version="v1", hyperparameters={},
            n_folds=4, embargo=5,
        )
        assert result["metrics"]["accuracy_oos"] > 0.8
        assert registry.list_models() == [result["model_id"]]
