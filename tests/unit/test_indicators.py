"""Tests des indicateurs (repli NumPy pur) — valeurs connues et alignées C++."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "python"))
from strategies import indicators as ind  # noqa: E402


def test_ema_known_values():
    # period=3 -> alpha=0.5 : [1,2,3] -> 1, 1.5, 2.25
    out = ind.ema(np.array([1.0, 2.0, 3.0]), 3)
    assert np.allclose(out, [1.0, 1.5, 2.25])


def test_ema_constant_series_is_constant():
    out = ind.ema(np.full(50, 5.0), 10)
    assert np.allclose(out, 5.0)


def test_rsi_monotonic_rise_is_100():
    out = ind.rsi(np.arange(30.0), 14)
    assert abs(out[-1] - 100.0) < 1e-6


def test_atr_flat_bars_equals_range():
    high, low, close = np.full(20, 10.5), np.full(20, 9.5), np.full(20, 10.0)
    assert abs(ind.atr(high, low, close, 14)[-1] - 1.0) < 1e-6


def test_indicators_length_preserved():
    x = np.linspace(1, 2, 40)
    assert len(ind.ema(x, 12)) == 40
    assert len(ind.rsi(x, 14)) == 40
    assert len(ind.atr(x, x, x, 14)) == 40
