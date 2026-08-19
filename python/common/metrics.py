"""Métriques Prometheus — implémentation minimale sans dépendance externe.

Produit le format d'exposition texte Prometheus (v0.0.4). Suffisant pour
Counter / Gauge / Histogram, thread-safe, et évite d'imposer ``prometheus_client``.
En production on peut basculer vers la lib officielle : l'interface (``inc``,
``set``, ``observe``) est volontairement compatible.

SRP : ce module ne fait que compter et rendre ; l'instrumentation métier vit
dans les services qui l'utilisent.
"""
from __future__ import annotations

import threading
from typing import Iterable


class _Metric:
    def __init__(self, name: str, help_text: str, mtype: str) -> None:
        self.name = name
        self.help = help_text
        self.type = mtype
        self._lock = threading.Lock()

    def _header(self) -> list[str]:
        return [f"# HELP {self.name} {self.help}", f"# TYPE {self.name} {self.type}"]


class Counter(_Metric):
    """Compteur monotone croissant."""

    def __init__(self, name: str, help_text: str) -> None:
        super().__init__(name, help_text, "counter")
        self._value = 0.0

    def inc(self, amount: float = 1.0) -> None:
        with self._lock:
            self._value += amount

    def render(self) -> list[str]:
        return [*self._header(), f"{self.name} {self._value}"]


class Gauge(_Metric):
    """Jauge : valeur instantanée pouvant monter ou descendre."""

    def __init__(self, name: str, help_text: str) -> None:
        super().__init__(name, help_text, "gauge")
        self._value = 0.0

    def set(self, value: float) -> None:
        with self._lock:
            self._value = float(value)

    def render(self) -> list[str]:
        return [*self._header(), f"{self.name} {self._value}"]


class Histogram(_Metric):
    """Histogramme à buckets cumulatifs (latences, tailles…)."""

    def __init__(self, name: str, help_text: str,
                 buckets: Iterable[float] = (0.005, 0.01, 0.05, 0.1, 0.5, 1, 5)) -> None:
        super().__init__(name, help_text, "histogram")
        self._bounds = sorted(buckets)
        self._counts = [0 for _ in self._bounds]
        self._sum = 0.0
        self._total = 0

    def observe(self, value: float) -> None:
        with self._lock:
            self._sum += value
            self._total += 1
            for i, bound in enumerate(self._bounds):
                if value <= bound:
                    self._counts[i] += 1

    def render(self) -> list[str]:
        lines = self._header()
        # _counts[i] est déjà cumulatif (obs <= bounds[i]) — conforme au format
        # Prometheus où chaque bucket `le` inclut tous les buckets inférieurs.
        for bound, count in zip(self._bounds, self._counts):
            lines.append(f'{self.name}_bucket{{le="{bound}"}} {count}')
        lines.append(f'{self.name}_bucket{{le="+Inf"}} {self._total}')
        lines.append(f"{self.name}_sum {self._sum}")
        lines.append(f"{self.name}_count {self._total}")
        return lines


class MetricsRegistry:
    """Collecte les métriques et rend l'exposition texte complète."""

    def __init__(self) -> None:
        self._metrics: list[_Metric] = []

    def register(self, metric: _Metric) -> _Metric:
        self._metrics.append(metric)
        return metric

    def counter(self, name: str, help_text: str) -> Counter:
        return self.register(Counter(name, help_text))  # type: ignore[return-value]

    def gauge(self, name: str, help_text: str) -> Gauge:
        return self.register(Gauge(name, help_text))  # type: ignore[return-value]

    def histogram(self, name: str, help_text: str, **kw) -> Histogram:
        return self.register(Histogram(name, help_text, **kw))  # type: ignore[return-value]

    def render(self) -> str:
        """Rend le document d'exposition (terminé par un saut de ligne)."""

        blocks = ["\n".join(m.render()) for m in self._metrics]
        return "\n".join(blocks) + "\n"


CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"
