# cicd/

Intégration et déploiement continus.

- `pipelines/` — définitions de pipelines (lint, build, tests, déploiement).
- `hooks/` — hooks de dépôt (pre-commit, checks de qualité locaux).

**Règle :** toute promotion vers un environnement passe par un pipeline ;
la config d'infrastructure ciblée vit dans `infrastructure/`.
