# python/

Cœur applicatif : recherche, pipelines de données, logique de stratégie et
orchestration de l'exécution. Code Python packageable et testable.

- `strategies/` — logique d'alpha et de gestion de position (signaux, sizing).
- `data/` — ingestion, nettoyage et normalisation des données de marché.
- `execution/` — routage d'ordres, gestion du risque temps réel, réconciliation.
- `research/` — prototypes et analyses exploratoires (pré-industrialisation).
- `common/` — utilitaires transverses (typing, config loader, horloge, I/O).

**Règle :** aucun secret en dur, aucune logique basse latence critique ici
(déléguée à `cpp/`). Tout module exposé est couvert par `tests/`.
