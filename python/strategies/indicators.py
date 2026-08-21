"""Indicateurs techniques.

Trois chemins possibles, interface identique (LSP) :
1. module natif C++ ``quant_native`` (pybind11) si présent — le plus rapide ;
2. repli **NumPy pur** (aucune dépendance externe, exécutable partout) ;

Les récurrences NumPy reproduisent exactement l'algorithme C++ (voir `cpp/`).
"""
from __future__ import annotations

import numpy as np

try:  # accélération native optionnelle
    import quant_native  # type: ignore

    _NATIVE = True
except ImportError:  # pragma: no cover - fallback pur Python
    _NATIVE = False


def _ewm(values: np.ndarray, alpha: float) -> np.ndarray:
    """Moyenne exponentielle récursive (adjust=False), NumPy pur.

    out[0] = values[0] ; out[i] = alpha*values[i] + (1-alpha)*out[i-1].
    """

    values = np.asarray(values, dtype=float)
    out = np.empty_like(values)
    if values.size == 0:
        return out
    out[0] = values[0]
    for i in range(1, values.size):
        out[i] = alpha * values[i] + (1.0 - alpha) * out[i - 1]
    return out


def ema(values: np.ndarray, period: int) -> np.ndarray:
    """Exponential Moving Average."""

    if _NATIVE:
        return np.asarray(quant_native.ema(values, period))
    return _ewm(values, 2.0 / (period + 1.0))


def rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    """Relative Strength Index (méthode de Wilder)."""

    if _NATIVE:
        return np.asarray(quant_native.rsi(close, period))
    close = np.asarray(close, dtype=float)
    delta = np.diff(close, prepend=close[0])
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = _ewm(gain, 1.0 / period)
    avg_loss = _ewm(loss, 1.0 / period)
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = np.where(avg_loss > 0, avg_gain / avg_loss, np.inf)
    return np.where(np.isinf(rs), 100.0, 100.0 - 100.0 / (1.0 + rs))


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """Average True Range (méthode de Wilder)."""

    if _NATIVE:
        return np.asarray(quant_native.atr(high, low, close, period))
    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)
    close = np.asarray(close, dtype=float)
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr = np.maximum.reduce([
        high - low,
        np.abs(high - prev_close),
        np.abs(low - prev_close),
    ])
    return _ewm(tr, 1.0 / period)


def native_available() -> bool:
    """Indique si l'accélération C++ est active (diagnostic/monitoring)."""

    return _NATIVE
