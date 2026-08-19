"""Orchestration du backtesting professionnel.

Fournit les *protocoles* de validation robuste — Walk-Forward, Out-of-Sample,
Monte Carlo, optimisation (grille + algorithme génétique) — indépendamment de
la stratégie évaluée (DIP : la stratégie est injectée via un callable).

Le moteur ne duplique pas la logique de trading : il consomme une fonction
``run_fn(params, data) -> equity_curve`` fournie par `python/strategies`.
"""
from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np

from .metrics import PerformanceReport, build_report, sharpe_ratio

# Une stratégie = fonction (paramètres, données) -> courbe d'equity.
RunFn = Callable[[dict[str, float], np.ndarray], np.ndarray]
ParamSpace = dict[str, Sequence[float]]


@dataclass(frozen=True)
class WalkForwardWindow:
    train: tuple[int, int]
    test: tuple[int, int]


def walk_forward_windows(n: int, train_size: int, test_size: int,
                         embargo: int = 0) -> list[WalkForwardWindow]:
    """Découpe glissante train/test avec embargo anti-fuite.

    L'embargo laisse un trou entre train et test pour éviter la contamination
    des observations chevauchantes (série temporelle).
    """

    windows: list[WalkForwardWindow] = []
    start = 0
    while start + train_size + embargo + test_size <= n:
        train = (start, start + train_size)
        test_start = train[1] + embargo
        windows.append(WalkForwardWindow(train, (test_start, test_start + test_size)))
        start += test_size
    return windows


def grid_search(run_fn: RunFn, space: ParamSpace, data: np.ndarray,
                objective: Callable[[np.ndarray], float] | None = None) -> dict:
    """Optimisation exhaustive ; objectif par défaut = Sharpe."""

    objective = objective or (lambda eq: sharpe_ratio(np.diff(eq) / eq[:-1]))
    keys = list(space)
    best_score, best_params = -np.inf, {}

    def _recurse(i: int, current: dict[str, float]) -> None:
        nonlocal best_score, best_params
        if i == len(keys):
            score = objective(run_fn(current, data))
            if score > best_score:
                best_score, best_params = score, dict(current)
            return
        for value in space[keys[i]]:
            _recurse(i + 1, {**current, keys[i]: value})

    _recurse(0, {})
    return {"params": best_params, "score": best_score}


def genetic_optimize(run_fn: RunFn, space: ParamSpace, data: np.ndarray,
                     objective: Callable[[np.ndarray], float] | None = None,
                     population: int = 20, generations: int = 15,
                     mutation_rate: float = 0.2, seed: int = 42) -> dict:
    """Algorithme génétique pour grands espaces de paramètres.

    Sélection élitiste + croisement uniforme + mutation. Utile quand la grille
    exhaustive explose combinatoirement.
    """

    rng = random.Random(seed)
    objective = objective or (lambda eq: sharpe_ratio(np.diff(eq) / eq[:-1]))
    keys = list(space)

    def random_individual() -> dict[str, float]:
        return {k: rng.choice(space[k]) for k in keys}

    def fitness(ind: dict[str, float]) -> float:
        return objective(run_fn(ind, data))

    pop = [random_individual() for _ in range(population)]
    best_ind, best_score = None, -np.inf

    for _ in range(generations):
        scored = sorted(pop, key=fitness, reverse=True)
        if (top := fitness(scored[0])) > best_score:
            best_score, best_ind = top, dict(scored[0])
        elite = scored[: max(2, population // 5)]
        children: list[dict[str, float]] = list(elite)
        while len(children) < population:
            a, b = rng.sample(elite, 2)
            child = {k: (a[k] if rng.random() < 0.5 else b[k]) for k in keys}
            for k in keys:
                if rng.random() < mutation_rate:
                    child[k] = rng.choice(space[k])
            children.append(child)
        pop = children

    return {"params": best_ind, "score": best_score}


def monte_carlo(returns: np.ndarray, n_paths: int = 1000, seed: int = 42) -> dict:
    """Bootstrap Monte-Carlo : distribution des résultats par ré-échantillonnage.

    Rééchantillonne les rendements observés pour estimer la dispersion du drawdown
    et du rendement final — mesure la robustesse au « chemin » et non à un tirage.
    """

    rng = np.random.default_rng(seed)
    returns = np.asarray(returns, dtype=float)
    finals, drawdowns = np.empty(n_paths), np.empty(n_paths)
    for i in range(n_paths):
        sample = rng.choice(returns, size=returns.size, replace=True)
        equity = np.cumprod(1 + sample)
        peak = np.maximum.accumulate(equity)
        finals[i] = equity[-1] - 1
        drawdowns[i] = float((-(equity - peak) / peak).max())
    return {
        "return_mean": float(finals.mean()),
        "return_p05": float(np.percentile(finals, 5)),
        "return_p95": float(np.percentile(finals, 95)),
        "drawdown_p95": float(np.percentile(drawdowns, 95)),
    }


def walk_forward_report(run_fn: RunFn, best_params: dict[str, float],
                        data: np.ndarray,
                        windows: list[WalkForwardWindow]) -> PerformanceReport:
    """Assemble une courbe d'equity out-of-sample et son rapport.

    Concatène les segments de test (jamais vus à l'optimisation) pour une mesure
    honnête de la performance.
    """

    segments: list[np.ndarray] = []
    for w in windows:
        oos = data[w.test[0]: w.test[1]]
        segments.append(run_fn(best_params, oos))
    equity = np.concatenate(segments) if segments else np.array([1.0])
    return build_report(equity)
