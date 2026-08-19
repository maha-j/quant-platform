# ml/

Chaîne d'apprentissage automatique.

- `features/` — définition et calcul des features (feature store logique).
- `models/` — artefacts de modèles versionnés / registre.
- `training/` — pipelines d'entraînement, validation et évaluation.
- `notebooks/` — exploration ; le code industrialisé migre vers `training/`.

**Règle :** entraînement reproductible (seed, versions data/features tracées).
