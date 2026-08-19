"""Tests du provider MetaTrader 5 via un faux client injecté (sans terminal).

`pandas` est requis par le provider ; le test est ignoré s'il est absent
(environnement minimal) et s'exécute en CI où pandas est installé.
"""
import asyncio
import sys
from pathlib import Path

import pytest

pytest.importorskip("pandas")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from common.config import MetaTrader5Config  # noqa: E402
from data.mt5 import MetaTrader5DataSource  # noqa: E402


def _rates(n: int) -> list[dict]:
    t0 = 1_600_000_000
    return [
        {"time": t0 + i * 900, "open": 1.10 + i * 1e-4, "high": 1.11 + i * 1e-4,
         "low": 1.09 + i * 1e-4, "close": 1.105 + i * 1e-4,
         "tick_volume": 100 + i, "spread": 2}
        for i in range(n)
    ]


class FakeMT5:
    """Sous-ensemble minimal du package MetaTrader5, piloté pour les tests."""

    TIMEFRAME_M15 = 15
    TIMEFRAME_H1 = 16

    def __init__(self, *, init_ok=True, select_ok=True, rates=None):
        self._init_ok, self._select_ok, self._rates = init_ok, select_ok, rates
        self.shutdown_called = False
        self.init_kwargs = None

    def initialize(self, **kwargs):
        self.init_kwargs = kwargs
        return self._init_ok

    def symbol_select(self, symbol, enable):
        return self._select_ok

    def copy_rates_from_pos(self, symbol, timeframe, start, count):
        if self._rates is None:
            return None
        return self._rates[:count]

    def last_error(self):
        return (-1, "fake error")

    def shutdown(self):
        self.shutdown_called = True


def _cfg(**kw):
    return MetaTrader5Config(**kw)


def test_connect_and_fetch_returns_ohlcv_frame():
    fake = FakeMT5(rates=_rates(50))
    ds = MetaTrader5DataSource.connect(_cfg(login=123, password="x", server="Broker"), client=fake)
    frame = asyncio.run(ds.fetch("EURUSD", "M15", 10))

    assert len(frame) == 10
    assert "volume" in frame.columns          # tick_volume renommé
    assert str(frame.index.dtype).startswith("datetime64")
    # Les identifiants ont bien été transmis à initialize().
    assert fake.init_kwargs["login"] == 123 and fake.init_kwargs["server"] == "Broker"


def test_connect_failure_raises():
    fake = FakeMT5(init_ok=False)
    with pytest.raises(ConnectionError):
        MetaTrader5DataSource.connect(_cfg(), client=fake)


def test_symbol_select_failure_raises():
    ds = MetaTrader5DataSource.connect(_cfg(), client=FakeMT5(select_ok=False, rates=_rates(5)))
    with pytest.raises(RuntimeError, match="symbol_select"):
        asyncio.run(ds.fetch("EURUSD", "M15", 5))


def test_empty_rates_raises():
    ds = MetaTrader5DataSource.connect(_cfg(), client=FakeMT5(rates=None))
    with pytest.raises(RuntimeError, match="copy_rates"):
        asyncio.run(ds.fetch("EURUSD", "M15", 5))


def test_unsupported_timeframe_raises():
    ds = MetaTrader5DataSource.connect(_cfg(), client=FakeMT5(rates=_rates(5)))
    with pytest.raises(ValueError, match="timeframe"):
        asyncio.run(ds.fetch("EURUSD", "X99", 5))


def test_context_manager_shuts_down():
    fake = FakeMT5(rates=_rates(5))
    with MetaTrader5DataSource.connect(_cfg(), client=fake) as ds:
        assert ds is not None
    assert fake.shutdown_called is True
