"""Moteur de Risk Management institutionnel.

Deux responsabilités séparées (SRP) :

1. :class:`PositionSizer` — *combien* trader (Risk per Trade, ATR sizing, Kelly).
2. :class:`RiskEngine`    — *a-t-on le droit* de trader (filtres + coupe-circuits).

Conception SOLID :
- Chaque filtre implémente :class:`RiskFilter` (OCP : on ajoute un filtre sans
  modifier le moteur ; ISP : interface minimale ``check``).
- Le moteur dépend de l'abstraction ``RiskFilter``, pas des implémentations (DIP).
- Toutes les bornes viennent de :class:`RiskLimits` (aucune valeur en dur).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone

from common.config import RiskLimits, VolatilityFilter


@dataclass(frozen=True)
class MarketSnapshot:
    """État de marché nécessaire aux filtres à l'instant de la décision."""

    symbol: str
    price: float
    spread_points: float
    atr: float
    atr_pct: float
    volume: float
    correlation_to_book: float
    minutes_to_news: float | None  # None = pas d'évènement proche


@dataclass
class AccountState:
    """État du compte suivi en continu par le moteur."""

    equity: float
    balance: float
    peak_equity: float
    day_start_equity: float
    week_start_equity: float
    open_positions: int
    day: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class RiskDecision:
    """Résultat d'une évaluation de risque."""

    approved: bool
    reasons: tuple[str, ...] = ()
    shutdown: bool = False


# --------------------------------------------------------------------------- #
# Dimensionnement de position                                                 #
# --------------------------------------------------------------------------- #
class PositionSizer:
    """Calcule la taille d'une position selon plusieurs méthodes."""

    def __init__(self, limits: RiskLimits) -> None:
        self._limits = limits

    def fixed_fractional(self, equity: float, stop_distance: float,
                         value_per_point: float) -> float:
        """Risk per Trade : risque un pourcentage fixe du capital.

        Args:
            equity: capital courant.
            stop_distance: distance au stop en points (> 0).
            value_per_point: valeur monétaire d'un point pour 1 lot.
        Returns:
            Taille en lots (>= 0).
        """

        if stop_distance <= 0 or value_per_point <= 0:
            return 0.0
        risk_amount = equity * self._limits.risk_per_trade_pct
        return risk_amount / (stop_distance * value_per_point)

    def atr_based(self, equity: float, atr: float, value_per_point: float) -> float:
        """ATR Position Sizing : le stop est un multiple d'ATR."""

        stop_distance = atr * self._limits.atr_risk_multiplier
        return self.fixed_fractional(equity, stop_distance, value_per_point)

    def kelly(self, equity: float, win_rate: float, payoff_ratio: float,
              value_per_point: float, stop_distance: float) -> float:
        """Kelly Criterion fractionnaire.

        f* = W - (1 - W) / R, borné à [0, 1] puis multiplié par ``kelly_fraction``
        (Kelly complet étant trop agressif en pratique).
        """

        if payoff_ratio <= 0:
            return 0.0
        kelly_full = win_rate - (1 - win_rate) / payoff_ratio
        kelly_full = max(0.0, min(1.0, kelly_full))
        risk_fraction = kelly_full * self._limits.kelly_fraction
        if stop_distance <= 0 or value_per_point <= 0:
            return 0.0
        return (equity * risk_fraction) / (stop_distance * value_per_point)


# --------------------------------------------------------------------------- #
# Filtres pré-trade (OCP)                                                      #
# --------------------------------------------------------------------------- #
class RiskFilter(ABC):
    """Contrat d'un filtre pré-trade."""

    name: str = "filter"

    @abstractmethod
    def check(self, market: MarketSnapshot, account: AccountState) -> str | None:
        """Retourne ``None`` si OK, sinon un motif de rejet."""


class SpreadFilter(RiskFilter):
    name = "spread"

    def __init__(self, limits: RiskLimits) -> None:
        self._max = limits.max_spread_points

    def check(self, market: MarketSnapshot, account: AccountState) -> str | None:
        if market.spread_points > self._max:
            return f"spread {market.spread_points:.1f} > {self._max:.1f}"
        return None


class SlippageFilter(RiskFilter):
    name = "slippage"

    def __init__(self, limits: RiskLimits) -> None:
        self._max = limits.max_slippage_points

    def check(self, market: MarketSnapshot, account: AccountState) -> str | None:
        # Le slippage réel est mesuré à l'exécution ; ici on borne l'attendu.
        expected = market.spread_points * 0.5
        if expected > self._max:
            return f"slippage attendu {expected:.1f} > {self._max:.1f}"
        return None


class VolatilityFilterRule(RiskFilter):
    name = "volatility"

    def __init__(self, vol: VolatilityFilter) -> None:
        self._vol = vol

    def check(self, market: MarketSnapshot, account: AccountState) -> str | None:
        if not (self._vol.min_atr_pct <= market.atr_pct <= self._vol.max_atr_pct):
            return f"atr_pct {market.atr_pct:.4f} hors [{self._vol.min_atr_pct}, {self._vol.max_atr_pct}]"
        return None


class LiquidityFilter(RiskFilter):
    name = "liquidity"

    def __init__(self, limits: RiskLimits) -> None:
        self._min = limits.min_liquidity_volume

    def check(self, market: MarketSnapshot, account: AccountState) -> str | None:
        if market.volume < self._min:
            return f"volume {market.volume:.0f} < {self._min:.0f}"
        return None


class CorrelationFilter(RiskFilter):
    name = "correlation"

    def __init__(self, limits: RiskLimits) -> None:
        self._max = limits.max_correlation

    def check(self, market: MarketSnapshot, account: AccountState) -> str | None:
        if abs(market.correlation_to_book) > self._max:
            return f"corrélation {market.correlation_to_book:.2f} > {self._max:.2f}"
        return None


class NewsFilter(RiskFilter):
    name = "news"

    def __init__(self, limits: RiskLimits) -> None:
        self._blackout = limits.news_blackout_minutes

    def check(self, market: MarketSnapshot, account: AccountState) -> str | None:
        if market.minutes_to_news is not None and market.minutes_to_news < self._blackout:
            return f"news dans {market.minutes_to_news:.0f} min < {self._blackout}"
        return None


class ExposureFilter(RiskFilter):
    name = "exposure"

    def __init__(self, limits: RiskLimits) -> None:
        self._max = limits.max_open_positions

    def check(self, market: MarketSnapshot, account: AccountState) -> str | None:
        if account.open_positions >= self._max:
            return f"positions ouvertes {account.open_positions} >= {self._max}"
        return None


# --------------------------------------------------------------------------- #
# Moteur de risque                                                            #
# --------------------------------------------------------------------------- #
class RiskEngine:
    """Orchestre filtres pré-trade + coupe-circuits de portefeuille.

    Les coupe-circuits (daily/weekly loss, drawdown, equity protection) sont des
    invariants globaux, évalués avant les filtres locaux ; s'ils sautent et que
    ``auto_shutdown`` est actif, le moteur exige l'arrêt du trading.
    """

    def __init__(self, limits: RiskLimits, vol: VolatilityFilter,
                 filters: list[RiskFilter] | None = None) -> None:
        self._limits = limits
        self._filters = filters or [
            ExposureFilter(limits),
            SpreadFilter(limits),
            SlippageFilter(limits),
            VolatilityFilterRule(vol),
            LiquidityFilter(limits),
            CorrelationFilter(limits),
            NewsFilter(limits),
        ]

    def circuit_breakers(self, account: AccountState) -> list[str]:
        """Vérifie les coupe-circuits globaux ; retourne les motifs violés."""

        breaches: list[str] = []
        daily_dd = 1 - account.equity / account.day_start_equity
        weekly_dd = 1 - account.equity / account.week_start_equity
        peak_dd = 1 - account.equity / account.peak_equity
        equity_floor = account.peak_equity * (1 - self._limits.equity_protection_pct)

        if daily_dd >= self._limits.max_daily_loss_pct:
            breaches.append(f"max daily loss atteint ({daily_dd:.2%})")
        if weekly_dd >= self._limits.max_weekly_loss_pct:
            breaches.append(f"max weekly loss atteint ({weekly_dd:.2%})")
        if peak_dd >= self._limits.max_drawdown_pct:
            breaches.append(f"max drawdown atteint ({peak_dd:.2%})")
        if account.equity <= equity_floor:
            breaches.append(f"equity protection déclenchée (< {equity_floor:.2f})")
        return breaches

    def evaluate(self, market: MarketSnapshot, account: AccountState) -> RiskDecision:
        """Décision complète pour un candidat de trade."""

        breaches = self.circuit_breakers(account)
        if breaches:
            return RiskDecision(
                approved=False,
                reasons=tuple(breaches),
                shutdown=self._limits.auto_shutdown,
            )

        rejections = [
            f"{f.name}: {reason}"
            for f in self._filters
            if (reason := f.check(market, account)) is not None
        ]
        return RiskDecision(approved=not rejections, reasons=tuple(rejections))
