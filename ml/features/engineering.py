"""Feature engineering — sans fuite de futur.

Chaque feature à l'instant ``t`` n'utilise que l'information disponible à ``t``.
Séparé du training (SRP) et réutilisable en live pour garantir la parité
train/inférence.
"""
from __future__ import annotations

import pandas as pd

# import relatif au package python/ (indicateurs partagés)
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2] / "python"))
from strategies import indicators  # noqa: E402


def build_features(ohlcv: pd.DataFrame) -> pd.DataFrame:
    """Construit une matrice de features à partir de barres OHLCV.

    Retourne un DataFrame aligné (les lignes initiales sans historique suffisant
    sont supprimées).
    """

    close = ohlcv["close"].to_numpy()
    high = ohlcv["high"].to_numpy()
    low = ohlcv["low"].to_numpy()

    feats = pd.DataFrame(index=ohlcv.index)
    feats["ret_1"] = pd.Series(close, index=ohlcv.index).pct_change()
    feats["ret_5"] = pd.Series(close, index=ohlcv.index).pct_change(5)
    feats["ema_ratio"] = indicators.ema(close, 12) / indicators.ema(close, 26) - 1
    feats["rsi_14"] = indicators.rsi(close, 14)
    feats["atr_pct"] = indicators.atr(high, low, close, 14) / close
    feats["realized_vol"] = feats["ret_1"].rolling(20).std()

    # Cible : signe du rendement futur (classification binaire), décalé -> pas de fuite.
    feats["target"] = (pd.Series(close, index=ohlcv.index).shift(-1) > close).astype(int)
    return feats.dropna()
