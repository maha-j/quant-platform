"""Tests unitaires du moteur de risque et du sizing."""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2] / "python"))
from common.config import RiskLimits, VolatilityFilter  # noqa: E402
from execution.risk import (AccountState, MarketSnapshot, PositionSizer,  # noqa: E402
                            RiskEngine)


def _account(equity=10_000.0):
    return AccountState(equity=equity, balance=equity, peak_equity=10_000.0,
                        day_start_equity=10_000.0, week_start_equity=10_000.0,
                        open_positions=0)


def _market(spread=1.0, atr_pct=0.01):
    return MarketSnapshot(symbol="EURUSD", price=1.1, spread_points=spread,
                          atr=0.001, atr_pct=atr_pct, volume=1000,
                          correlation_to_book=0.1, minutes_to_news=None)


def test_daily_loss_triggers_shutdown():
    engine = RiskEngine(RiskLimits(), VolatilityFilter())
    acct = _account(equity=9_700.0)  # -3 % > max_daily_loss 2 %
    decision = engine.evaluate(_market(), acct)
    assert not decision.approved
    assert decision.shutdown is True


def test_spread_filter_rejects():
    engine = RiskEngine(RiskLimits(), VolatilityFilter())
    decision = engine.evaluate(_market(spread=999.0), _account())
    assert not decision.approved
    assert any("spread" in r for r in decision.reasons)


def test_clean_market_is_approved():
    engine = RiskEngine(RiskLimits(), VolatilityFilter())
    assert engine.evaluate(_market(), _account()).approved


def test_atr_sizing_scales_with_equity():
    sizer = PositionSizer(RiskLimits())
    small = sizer.atr_based(1_000, atr=0.001, value_per_point=10)
    big = sizer.atr_based(10_000, atr=0.001, value_per_point=10)
    assert big > small > 0
