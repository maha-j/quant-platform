# cpp/

Composants haute performance / basse latence appelés depuis Python via bindings.

- `src/` — implémentations (moteur d'exécution, calculs de risque, order book).
- `include/` — en-têtes publics (interface stable consommée par `src` et bindings).
- `bindings/` — liaisons Python (pybind11) exposant les modules critiques.

**Règle :** frontière stricte via `include/` ; toute API exposée à Python est
documentée et testée. Compilation reproductible (voir `infrastructure/docker`).
