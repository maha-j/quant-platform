"""Indicateurs techniques.

Implémentation de référence NumPy/Pandas. Les chemins critiques (ATR/EMA/RSI)
peuvent être délégués au module natif C++ ``quant_native`` (pybind11) quand il
est disponible — l'interface reste identique (LSP : substituable sans changement
d'appelant). Voir `cpp/`.
"""
from __future__ import annotations

import numpy as np

try:  # accélération native optionnelle
    import quant_native  # type: ignore

    _NATIVE = True
except ImportError:  # pragma: no cover - fallback pur Python
    _NATIVE = False


def ema(values: np.ndarray, period: int) -> np.ndarray:
    """Exponential Moving Average."""

    if _NATIVE:
        return np.asarray(quant_native.ema(values, period))
    import pandas as pd  # import paresseux : non requis si accélération native

    return pd.Series(values).ewm(span=period, adjust=False).mean().to_numpy()


def rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    """Relative Strength Index (méthode de Wilder)."""

    if _NATIVE:
        return np.asarray(quant_native.rsi(close, period))
    import pandas as pd

    delta = np.diff(close, prepend=close[0])
    gain = pd.Series(np.where(delta > 0, delta, 0.0))
    loss = pd.Series(np.where(delta < 0, -delta, 0.0))
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(100).to_numpy()


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """Average True Range (méthode de Wilder)."""

    if _NATIVE:
        return np.asarray(quant_native.atr(high, low, close, period))
    import pandas as pd

    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr = np.maximum.reduce([
        high - low,
        np.abs(high - prev_close),
        np.abs(low - prev_close),
    ])
    return pd.Series(tr).ewm(alpha=1 / period, adjust=False).mean().to_numpy()


def native_available() -> bool:
    """Indique si l'accélération C++ est active (diagnostic/monitoring)."""

    return _NATIVE
