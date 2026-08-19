"""Gestion du portefeuille.

Suit les positions ouvertes, l'exposition agrégée et applique le
dimensionnement (via :class:`PositionSizer`) sous le contrôle du
:class:`RiskEngine`. SRP : cet objet ne décide pas *du signal*, seulement de
*la traduction d'un signal validé en ordre dimensionné*.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from common.config import RiskLimits
from strategies.signals import Signal, Side

from .risk import (AccountState, MarketSnapshot, PositionSizer, RiskDecision,
                   RiskEngine)


@dataclass
class Position:
    symbol: str
    side: Side
    size: float
    entry: float


@dataclass
class OrderIntent:
    """Ordre dimensionné prêt à être transmis à l'exécution/MQL5."""

    symbol: str
    side: Side
    size: float
    stop_distance: float
    decision: RiskDecision


@dataclass
class Portfolio:
    """État et logique de dimensionnement du portefeuille."""

    limits: RiskLimits
    risk_engine: RiskEngine
    value_per_point: float = 10.0
    positions: dict[str, Position] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._sizer = PositionSizer(self.limits)

    def build_order(self, signal: Signal, market: MarketSnapshot,
                    account: AccountState) -> OrderIntent | None:
        """Transforme un signal validé en ordre dimensionné, ou refuse.

        Returns ``None`` si le signal est plat ou rejeté par le risque.
        """

        if signal.side is Side.FLAT:
            return None

        decision = self.risk_engine.evaluate(market, account)
        if not decision.approved:
            return OrderIntent(signal.symbol, signal.side, 0.0, 0.0, decision)

        size = self._sizer.atr_based(account.equity, signal.atr, self.value_per_point)
        stop_distance = signal.atr * self.limits.atr_risk_multiplier
        return OrderIntent(signal.symbol, signal.side, size, stop_distance, decision)

    def apply_fill(self, symbol: str, side: Side, size: float, price: float) -> None:
        """Met à jour l'état après confirmation d'exécution (fill)."""

        if size <= 0:
            self.positions.pop(symbol, None)
            return
        self.positions[symbol] = Position(symbol, side, size, price)

    @property
    def open_count(self) -> int:
        return len(self.positions)
