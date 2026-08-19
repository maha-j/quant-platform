"""Tests unitaires des métriques de performance."""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.append(str(Path(__file__).resolve().parents[2] / "backtests"))
from engine import metrics  # noqa: E402


def test_report_on_growing_equity():
    equity = np.array([100.0, 101.0, 103.0, 102.0, 105.0])
    report = metrics.build_report(equity)
    assert report.total_return > 0
    assert report.max_drawdown >= 0
    assert report.n_trades == 4
    assert set(report.to_dict()) == {
        "sharpe", "sortino", "profit_factor", "recovery_factor",
        "max_drawdown", "ulcer_index", "expectancy", "win_rate",
        "total_return", "n_trades",
    }


def test_max_drawdown_flat_is_zero():
    assert metrics.max_drawdown(np.array([100.0, 100.0, 100.0])) == 0.0


def test_export_is_strict_json_safe():
    # Equity strictement croissante -> aucun drawdown/perte -> facteurs infinis.
    equity = np.array([100.0, 101.0, 102.0, 103.0])
    d = metrics.build_report(equity).to_dict()
    assert d["profit_factor"] is None       # inf remplacé par null
    assert d["recovery_factor"] is None
    # allow_nan=False rejette Infinity/NaN : garantit un JSON standard.
    json.dumps(d, allow_nan=False)


def test_recovery_factor_uses_peak_drawdown():
    # Pic à 120 puis creux 90 : DD devise = 30 ; profit net = 110-100 = 10.
    equity = np.array([100.0, 120.0, 90.0, 110.0])
    assert metrics.recovery_factor(equity) == 10.0 / 30.0
