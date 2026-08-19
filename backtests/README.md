# backtests/

Validation historique des stratégies.

- `engine/` — moteur de simulation (event loop, modèle de coûts, slippage).
- `scenarios/` — définitions de backtests (période, univers, paramètres).
- `results/` — sorties générées (métriques, courbes) — **ignoré par Git**.

**Règle :** le moteur consomme les stratégies de `python/strategies` sans les
dupliquer ; parité stricte entre logique backtest et live.
