"""Service d'exécution : API de contrôle (FastAPI) + publication des signaux.

- FastAPI expose le contrôle/observabilité (santé, dernier signal, arrêt).
- Le transport temps réel vers MQL5 passe par ZeroMQ (voir
  docs/architecture/communication.md) — REST sert au contrôle, pas au chemin
  chaud.

Le payload signé (HMAC) garantit l'intégrité côté EA.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time

from fastapi import FastAPI, Response
from pydantic import BaseModel

from common.config import Settings, load_settings
from common.metrics import CONTENT_TYPE, MetricsRegistry
from strategies.signals import Signal, Side


def sign_payload(payload: dict, secret: str) -> str:
    """HMAC-SHA256 du payload canonique (anti-altération)."""

    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


class SignalEnvelope(BaseModel):
    """Enveloppe transmise à l'EA : signal + métadonnées de sécurité/TTL."""

    signal: Signal
    signal_id: str
    issued_at: float
    ttl: int
    signature: str

    @classmethod
    def wrap(cls, signal: Signal, settings: Settings) -> "SignalEnvelope":
        issued_at = time.time()
        signal_id = hashlib.sha1(
            f"{signal.symbol}{issued_at}".encode()
        ).hexdigest()[:16]
        payload = {"signal": signal.model_dump(mode="json"),
                   "signal_id": signal_id, "issued_at": issued_at}
        return cls(
            signal=signal,
            signal_id=signal_id,
            issued_at=issued_at,
            ttl=settings.messaging.signal_ttl_seconds,
            signature=sign_payload(payload, settings.messaging.hmac_secret),
        )


class RiskState(BaseModel):
    """Instantané de risque poussé vers l'observabilité (support des alertes)."""

    equity: float
    drawdown_pct: float = 0.0
    daily_loss_pct: float = 0.0
    open_positions: int = 0
    circuit_breaker_active: bool = False
    trading_halted: bool = False


def create_app(settings: Settings | None = None) -> FastAPI:
    """Fabrique l'application (injection de config pour les tests)."""

    settings = settings or load_settings()
    app = FastAPI(title="Quant Execution Service", version="0.1.0")
    state: dict[str, SignalEnvelope | None] = {"last": None}

    # --- Instrumentation Prometheus (boucle monitoring) ---------------------
    registry = MetricsRegistry()
    signals_total = registry.counter(
        "quant_signals_published_total", "Nombre de signaux publiés.")
    rejected_total = registry.counter(
        "quant_signals_flat_total", "Nombre de signaux plats (non actionnables).")
    last_confidence = registry.gauge(
        "quant_last_signal_confidence", "Confiance du dernier signal.")
    publish_latency = registry.histogram(
        "quant_publish_latency_seconds", "Latence de traitement d'un signal.")
    # État de risque poussé par la boucle d'exécution (support des alertes).
    g_equity = registry.gauge("quant_equity", "Equity courante du compte.")
    g_drawdown = registry.gauge("quant_drawdown_pct", "Drawdown depuis le pic (fraction).")
    g_daily_loss = registry.gauge("quant_daily_loss_pct", "Perte du jour (fraction).")
    g_positions = registry.gauge("quant_open_positions", "Positions ouvertes.")
    g_breaker = registry.gauge("quant_circuit_breaker_active", "Coupe-circuit actif (1/0).")
    g_halted = registry.gauge("quant_trading_halted", "Trading gelé (1/0).")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.environment.value}

    @app.post("/signals")
    def publish(signal: Signal) -> SignalEnvelope:
        """Signe, mémorise et retourne l'enveloppe (à router vers ZeroMQ)."""

        start = time.perf_counter()
        envelope = SignalEnvelope.wrap(signal, settings)
        state["last"] = envelope
        signals_total.inc()
        if signal.side is Side.FLAT:
            rejected_total.inc()
        last_confidence.set(signal.confidence)
        publish_latency.observe(time.perf_counter() - start)
        return envelope

    @app.get("/signals/last")
    def last() -> SignalEnvelope | None:
        return state["last"]

    @app.post("/risk/state")
    def push_risk_state(rs: RiskState) -> dict[str, str]:
        """Reçoit l'état de risque de la boucle d'exécution et le publie en métriques.

        Permet à Prometheus/Alertmanager de surveiller equity, drawdown,
        coupe-circuits et gel du trading (voir monitoring/alerts/).
        """

        g_equity.set(rs.equity)
        g_drawdown.set(rs.drawdown_pct)
        g_daily_loss.set(rs.daily_loss_pct)
        g_positions.set(rs.open_positions)
        g_breaker.set(1.0 if rs.circuit_breaker_active else 0.0)
        g_halted.set(1.0 if rs.trading_halted else 0.0)
        return {"status": "ok"}

    @app.get("/metrics")
    def metrics() -> Response:
        """Exposition Prometheus (scrapée par monitoring/prometheus)."""

        return Response(content=registry.render(), media_type=CONTENT_TYPE)

    return app


app = create_app()
