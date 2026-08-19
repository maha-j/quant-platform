# database/

Schéma et cycle de vie de la base (séries temporelles, ordres, positions, PnL).

- `migrations/` — migrations versionnées (schéma source de vérité).
- `schemas/` — définitions/DDL de référence et diagrammes.
- `seeds/` — données de référence (instruments, calendriers, symboles).

**Règle :** toute évolution de schéma passe par une migration ; jamais d'ALTER
manuel en production.
