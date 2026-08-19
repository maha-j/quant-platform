"""Tests du registre Prometheus maison et de l'endpoint /metrics."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from fastapi.testclient import TestClient  # noqa: E402

from common.config import Settings  # noqa: E402
from common.metrics import MetricsRegistry  # noqa: E402
from execution.service import RiskState, create_app  # noqa: E402
from strategies.signals import Signal, Side  # noqa: E402


def test_registry_render_format():
    reg = MetricsRegistry()
    c = reg.counter("orders_total", "Nb ordres")
    g = reg.gauge("equity", "Equity")
    c.inc()
    c.inc(2)
    g.set(10_000)
    text = reg.render()
    assert "# TYPE orders_total counter" in text
    assert "orders_total 3.0" in text
    assert "equity 10000.0" in text


def test_metrics_endpoint_counts_signals():
    app = create_app(Settings())
    client = TestClient(app)

    buy = Signal(symbol="EURUSD", side=Side.BUY, confidence=0.8, atr=0.001)
    flat = Signal(symbol="EURUSD", side=Side.FLAT, confidence=0.0, atr=0.001)
    assert client.post("/signals", json=buy.model_dump(mode="json")).status_code == 200
    assert client.post("/signals", json=flat.model_dump(mode="json")).status_code == 200

    body = client.get("/metrics").text
    assert "quant_signals_published_total 2.0" in body
    assert "quant_signals_flat_total 1.0" in body
    assert "quant_last_signal_confidence 0.0" in body  # dernier = flat
    assert "quant_publish_latency_seconds_count 2" in body


def test_risk_state_endpoint_exposes_metrics():
    app = create_app(Settings())
    client = TestClient(app)

    rs = RiskState(equity=9500.0, drawdown_pct=0.12, daily_loss_pct=0.02,
                   open_positions=3, circuit_breaker_active=True,
                   trading_halted=True)
    assert client.post("/risk/state", json=rs.model_dump()).status_code == 200

    body = client.get("/metrics").text
    assert "quant_equity 9500.0" in body
    assert "quant_drawdown_pct 0.12" in body
    assert "quant_circuit_breaker_active 1.0" in body
    assert "quant_trading_halted 1.0" in body
    assert "quant_open_positions 3.0" in body
