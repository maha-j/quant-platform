"""Logging structuré (JSON) commun à toute la plateforme.

Sorties destinées à `logs/` au runtime et expédiables vers la stack
d'observabilité (`monitoring/`). Un seul point de configuration évite les
divergences de format entre modules.

``structlog`` est la dépendance cible (rendu JSON structuré). S'il est absent
(environnement minimal), on dégrade proprement vers la ``logging`` standard avec
une interface compatible (``log.info("msg", clé=valeur)``) — même contrat pour
les appelants, comme le reste des dépendances optionnelles de la plateforme.
"""
from __future__ import annotations

import logging
import sys

try:
    import structlog

    _STRUCTLOG = True
except ImportError:  # pragma: no cover - repli minimal
    _STRUCTLOG = False


class _StdlibBoundLogger:
    """Adaptateur minimal exposant l'API structlog sur la lib standard.

    Les paires clé=valeur sont sérialisées ``clé=valeur`` en fin de message.
    """

    def __init__(self, name: str) -> None:
        self._log = logging.getLogger(name)

    def _emit(self, level: int, event: str, **kw: object) -> None:
        suffix = " ".join(f"{k}={v}" for k, v in kw.items())
        self._log.log(level, "%s %s" % (event, suffix) if suffix else event)

    def debug(self, event: str, **kw: object) -> None: self._emit(logging.DEBUG, event, **kw)
    def info(self, event: str, **kw: object) -> None: self._emit(logging.INFO, event, **kw)
    def warning(self, event: str, **kw: object) -> None: self._emit(logging.WARNING, event, **kw)
    def error(self, event: str, **kw: object) -> None: self._emit(logging.ERROR, event, **kw)
    # Alias structlog courant.
    warn = warning


def configure_logging(level: str = "INFO", json: bool = True) -> None:
    """Configure le logging global (idempotent).

    Args:
        level: niveau racine (``DEBUG``…``CRITICAL``).
        json:  si vrai, rendu JSON ligne-à-ligne (prod) ; sinon rendu console.
               Sans structlog, le repli produit toujours du texte simple.
    """

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)
    if not _STRUCTLOG:
        return

    renderer = (
        structlog.processors.JSONRenderer()
        if json
        else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(level)
        ),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str):
    """Retourne un logger nommé (structlog si dispo, sinon repli stdlib)."""

    if _STRUCTLOG:
        return structlog.get_logger(name)
    return _StdlibBoundLogger(name)
