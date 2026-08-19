# config/

Configuration **déclarative** uniquement. Aucun code exécutable.

- `environments/` — paramètres par environnement (dev, staging, prod).
- `strategies/` — paramètres et bornes de risque par stratégie.
- `secrets/` — placeholders et templates ; contenu réel **ignoré par Git**.

**Règle :** les secrets réels vivent dans un gestionnaire (Vault / SSM), jamais
commités. `secrets/` ne contient que des `*.example`.
