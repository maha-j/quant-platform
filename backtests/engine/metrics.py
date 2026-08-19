"""Statistiques de performance — toutes exportables.

Fonctions pures NumPy sur une série de rendements (ou une courbe d'equity).
Séparées de l'orchestration (SRP) : réutilisables en backtest *et* en live.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np

TRADING_DAYS = 252


def _to_returns(equity: np.ndarray) -> np.ndarray:
    """Rendements simples à partir d'une courbe d'equity."""

    equity = np.asarray(equity, dtype=float)
    return np.diff(equity) / equity[:-1]


def sharpe_ratio(returns: np.ndarray, rf: float = 0.0, periods: int = TRADING_DAYS) -> float:
    """Sharpe annualisé."""

    r = np.asarray(returns, dtype=float) - rf / periods
    sd = r.std(ddof=1)
    return float(np.sqrt(periods) * r.mean() / sd) if sd > 0 else 0.0


def sortino_ratio(returns: np.ndarray, rf: float = 0.0, periods: int = TRADING_DAYS) -> float:
    """Sortino annualisé (ne pénalise que la volatilité baissière)."""

    r = np.asarray(returns, dtype=float) - rf / periods
    downside = r[r < 0]
    dd = np.sqrt(np.mean(downside**2)) if downside.size else 0.0
    return float(np.sqrt(periods) * r.mean() / dd) if dd > 0 else 0.0


def max_drawdown(equity: np.ndarray) -> float:
    """Drawdown maximal (fraction, ex. 0.2 = -20 %)."""

    equity = np.asarray(equity, dtype=float)
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak
    return float(-dd.min()) if dd.size else 0.0


def profit_factor(returns: np.ndarray) -> float:
    """Somme des gains / somme absolue des pertes."""

    r = np.asarray(returns, dtype=float)
    gains = r[r > 0].sum()
    losses = -r[r < 0].sum()
    return float(gains / losses) if losses > 0 else float("inf")


def expectancy(returns: np.ndarray) -> float:
    """Gain moyen espéré par trade."""

    r = np.asarray(returns, dtype=float)
    return float(r.mean()) if r.size else 0.0


def recovery_factor(equity: np.ndarray) -> float:
    """Profit net / drawdown maximal en devise (efficacité de récupération).

    Le drawdown en devise est ``max(pic - equity)`` (mesuré depuis le pic
    courant), et non ``max_drawdown × capital_initial`` qui le sous-estime dès
    que le pic dépasse le capital de départ.
    """

    equity = np.asarray(equity, dtype=float)
    net = equity[-1] - equity[0]
    peak = np.maximum.accumulate(equity)
    mdd_currency = float((peak - equity).max()) if equity.size else 0.0
    return float(net / mdd_currency) if mdd_currency > 0 else float("inf")


def ulcer_index(equity: np.ndarray) -> float:
    """Ulcer Index : RMS des drawdowns (mesure la douleur, pas la volatilité)."""

    equity = np.asarray(equity, dtype=float)
    peak = np.maximum.accumulate(equity)
    drawdown_pct = (equity - peak) / peak * 100
    return float(np.sqrt(np.mean(drawdown_pct**2))) if equity.size else 0.0


def win_rate(returns: np.ndarray) -> float:
    r = np.asarray(returns, dtype=float)
    return float((r > 0).mean()) if r.size else 0.0


@dataclass(frozen=True)
class PerformanceReport:
    """Rapport agrégé exportable (``to_dict`` → JSON/CSV)."""

    sharpe: float
    sortino: float
    profit_factor: float
    recovery_factor: float
    max_drawdown: float
    ulcer_index: float
    expectancy: float
    win_rate: float
    total_return: float
    n_trades: int

    def to_dict(self) -> dict[str, float | int | None]:
        """Export JSON-sûr : les valeurs non finies (``inf``/``nan``) → ``None``.

        ``profit_factor``/``recovery_factor`` valent ``inf`` en l'absence de perte
        ou de drawdown ; ``Infinity`` n'étant pas du JSON standard, on l'expose
        comme ``null`` pour rester interopérable (fichiers, API, BI).
        """

        return {
            k: (v if not isinstance(v, float) or math.isfinite(v) else None)
            for k, v in asdict(self).items()
        }


def build_report(equity: np.ndarray) -> PerformanceReport:
    """Construit le rapport complet à partir d'une courbe d'equity."""

    equity = np.asarray(equity, dtype=float)
    returns = _to_returns(equity)
    total = float(equity[-1] / equity[0] - 1) if equity.size > 1 else 0.0
    return PerformanceReport(
        sharpe=sharpe_ratio(returns),
        sortino=sortino_ratio(returns),
        profit_factor=profit_factor(returns),
        recovery_factor=recovery_factor(equity),
        max_drawdown=max_drawdown(equity),
        ulcer_index=ulcer_index(equity),
        expectancy=expectancy(returns),
        win_rate=win_rate(returns),
        total_return=total,
        n_trades=int(returns.size),
    )
