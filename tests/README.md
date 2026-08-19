# tests/

Suites de tests transverses (Python, bindings C++, contrats).

- `unit/` — tests unitaires isolés.
- `integration/` — bout-en-bout entre composants (data → stratégie → exécution).
- `performance/` — latence et débit des chemins critiques.

**Règle :** exécutés en `cicd/` ; aucun merge sans suite verte.
