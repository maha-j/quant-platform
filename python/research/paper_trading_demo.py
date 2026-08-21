"""Simulateur de trading démo (paper trading) — projet global en action.

Branche les composants **réels** de la plateforme sur des données de marché :
provider REST → stratégie (EmaRsiStrategy) → moteur de risque (RiskEngine) →
dimensionnement (Portfolio/PositionSizer) → exécution simulée (fills sur SL/TP).

Aucun broker requis : les ordres sont exécutés en simulation (démo). Si le
service FastAPI tourne sur http://127.0.0.1:8000, chaque signal et l'état de
risque y sont poussés → visibles dans /metrics (Prometheus/Grafana).

Lancer :  PYTHONPATH="$PWD/python:$PWD" python python/research/paper_trading_demo.py
"""
from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "python"))

from common.config import RiskLimits, VolatilityFilter  # noqa: E402
from execution.portfolio import Portfolio  # noqa: E402
from execution.risk import AccountState, MarketSnapshot, RiskEngine  # noqa: E402
from research.rest_end_to_end import bars_to_arrays, fetch_bars  # noqa: E402
from strategies.signals import EmaRsiStrategy, Side  # noqa: E402

SERVICE_URL = "http://127.0.0.1:8000"
SYMBOL = "EURUSD"
START_EQUITY = 10_000.0
VALUE_PER_POINT = 10.0
WARMUP = 60


@dataclass
class OpenPosition:
    side: Side
    size: float
    entry: float
    sl: float
    tp: float


@dataclass
class Book:
    equity: float = START_EQUITY
    peak: float = START_EQUITY
    day_start: float = START_EQUITY
    trades: int = 0
    wins: int = 0
    position: OpenPosition | None = None
    log: list[str] = field(default_factory=list)

    @property
    def drawdown(self) -> float:
        return max(0.0, 1 - self.equity / self.peak)


def _push(client, path: str, payload: dict) -> None:
    """Pousse vers le service live si joignable (silencieux sinon)."""

    if client is None:
        return
    try:
        client.post(f"{SERVICE_URL}{path}", json=payload, timeout=1.0)
    except Exception:  # noqa: BLE001 - le service est optionnel
        pass


def run(bars: dict[str, np.ndarray]) -> Book:
    close, high, low = bars["close"], bars["high"], bars["low"]
    n = len(close)

    limits = RiskLimits()
    engine = RiskEngine(limits, VolatilityFilter())
    portfolio = Portfolio(limits=limits, risk_engine=engine, value_per_point=VALUE_PER_POINT)
    strategy = EmaRsiStrategy()
    book = Book()

    try:
        import httpx

        client = httpx.Client()
    except Exception:  # noqa: BLE001
        client = None

    for i in range(WARMUP, n):
        # 1) Gestion de la position ouverte : SL/TP touchés sur la barre courante.
        if book.position is not None:
            p = book.position
            exit_price = None
            if p.side is Side.BUY:
                if low[i] <= p.sl:
                    exit_price = p.sl
                elif high[i] >= p.tp:
                    exit_price = p.tp
            else:
                if high[i] >= p.sl:
                    exit_price = p.sl
                elif low[i] <= p.tp:
                    exit_price = p.tp
            if exit_price is not None:
                direction = 1.0 if p.side is Side.BUY else -1.0
                pnl = direction * (exit_price - p.entry) * VALUE_PER_POINT * p.size
                book.equity += pnl
                book.peak = max(book.peak, book.equity)
                book.trades += 1
                if pnl > 0:
                    book.wins += 1
                book.log.append(
                    f"#{book.trades:03d} {p.side.value:4s} clôturé @ {exit_price:.5f} "
                    f"PnL={pnl:+.2f} equity={book.equity:.2f}")
                book.position = None

        # 2) Génération d'un signal sur l'historique disponible (pas de fuite).
        sig = strategy.generate(SYMBOL, high[: i + 1], low[: i + 1], close[: i + 1])
        _push(client, "/signals", {"symbol": SYMBOL, "side": sig.side.value,
                                   "confidence": sig.confidence, "atr": sig.atr})

        # 3) Nouvelle entrée si à plat, signal actionnable et risque validé.
        if book.position is None and sig.side is not Side.FLAT:
            market = MarketSnapshot(
                symbol=SYMBOL, price=float(close[i]), spread_points=1.0,
                atr=sig.atr, atr_pct=sig.atr / float(close[i]), volume=1000.0,
                correlation_to_book=0.0, minutes_to_news=None)
            account = AccountState(
                equity=book.equity, balance=book.equity, peak_equity=book.peak,
                day_start_equity=book.day_start, week_start_equity=book.day_start,
                open_positions=0)
            order = portfolio.build_order(sig, market, account)
            if order is not None and order.decision.approved and order.size > 0:
                entry = float(close[i])
                direction = 1.0 if sig.side is Side.BUY else -1.0
                sl = entry - direction * order.stop_distance
                tp = entry + direction * 2 * order.stop_distance  # RR 2:1
                book.position = OpenPosition(sig.side, order.size, entry, sl, tp)

        # 4) Télémétrie de risque vers le service (observabilité live).
        if i % 25 == 0:
            _push(client, "/risk/state", {
                "equity": round(book.equity, 2),
                "drawdown_pct": round(book.drawdown, 4),
                "daily_loss_pct": round(max(0.0, 1 - book.equity / book.day_start), 4),
                "open_positions": 1 if book.position else 0,
                "circuit_breaker_active": bool(engine.circuit_breakers(AccountState(
                    book.equity, book.equity, book.peak, book.day_start,
                    book.day_start, 0))),
                "trading_halted": False})

    if client is not None:
        client.close()
    return book


def main() -> None:
    bars_list = asyncio.run(fetch_bars(SYMBOL, "M15", 3000))
    bars = bars_to_arrays(bars_list)
    print(f"provider REST : {len(bars_list)} barres · symbole {SYMBOL}")
    print(f"capital initial : {START_EQUITY:.2f}\n")

    book = run(bars)

    print("— derniers trades —")
    for line in book.log[-8:]:
        print(" ", line)
    win_rate = book.wins / book.trades if book.trades else 0.0
    ret = book.equity / START_EQUITY - 1
    print("\n— résumé démo —")
    print(f"  trades        : {book.trades}")
    print(f"  gagnants      : {book.wins} ({win_rate:.1%})")
    print(f"  equity finale : {book.equity:.2f}")
    print(f"  rendement     : {ret:+.2%}")
    print(f"  drawdown max  : {book.drawdown:.2%}")


if __name__ == "__main__":
    main()
