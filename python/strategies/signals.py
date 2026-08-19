"""Génération de signaux.

Interface :class:`Strategy` (OCP/LSP) : on ajoute une stratégie sans toucher au
reste du système. Un signal est une donnée immuable et sérialisable (Pydantic),
prête à être publiée vers l'EA MQL5 (voir `python/execution`).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum

import numpy as np
from pydantic import BaseModel, Field

from . import indicators


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"
    FLAT = "flat"


class Signal(BaseModel):
    """Signal validé, contrat d'échange avec l'exécution/MQL5."""

    schema_version: int = 1
    symbol: str
    side: Side
    confidence: float = Field(ge=0, le=1)
    atr: float = Field(ge=0)
    reason: str = ""


class Strategy(ABC):
    """Contrat d'une stratégie : produit un signal à partir de barres OHLC."""

    @abstractmethod
    def generate(self, symbol: str, high: np.ndarray, low: np.ndarray,
                 close: np.ndarray) -> Signal:
        ...


class EmaRsiStrategy(Strategy):
    """Croisement EMA rapide/lente filtré par RSI (exemple de référence)."""

    def __init__(self, fast: int = 12, slow: int = 26, rsi_period: int = 14,
                 rsi_buy: float = 55.0, rsi_sell: float = 45.0) -> None:
        self._fast, self._slow = fast, slow
        self._rsi_period, self._rsi_buy, self._rsi_sell = rsi_period, rsi_buy, rsi_sell

    def generate(self, symbol: str, high: np.ndarray, low: np.ndarray,
                 close: np.ndarray) -> Signal:
        ema_fast = indicators.ema(close, self._fast)
        ema_slow = indicators.ema(close, self._slow)
        rsi_val = indicators.rsi(close, self._rsi_period)
        atr_val = indicators.atr(high, low, close)

        spread = ema_fast[-1] - ema_slow[-1]
        confidence = float(min(1.0, abs(spread) / (atr_val[-1] + 1e-9)))

        if spread > 0 and rsi_val[-1] >= self._rsi_buy:
            side, reason = Side.BUY, "ema_fast>ema_slow & rsi haussier"
        elif spread < 0 and rsi_val[-1] <= self._rsi_sell:
            side, reason = Side.SELL, "ema_fast<ema_slow & rsi baissier"
        else:
            side, reason, confidence = Side.FLAT, "pas de confluence", 0.0

        return Signal(symbol=symbol, side=side, confidence=confidence,
                      atr=float(atr_val[-1]), reason=reason)
