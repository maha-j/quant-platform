# scripts/

Scripts d'exploitation ponctuels ou planifiés (non applicatifs).

- `deploy/` — orchestration de déploiement et rollback.
- `data/` — chargement, backfill et réparation de données.
- `maintenance/` — tâches récurrentes (purge, réindexation, sauvegardes).

**Règle :** idempotents, journalisés, sans logique métier de stratégie.
