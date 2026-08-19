# Moteur IA — Comparatif des modèles & pipeline

## 1. Comparatif des familles de modèles

| Modèle          | Type de donnée cible          | Force principale                    | Faiblesse                     | Latence inférence | Interprétabilité |
|-----------------|-------------------------------|-------------------------------------|-------------------------------|-------------------|------------------|
| **XGBoost**     | Features tabulaires           | Référence sur données tabulaires, robuste, rapide à entraîner | Ne modélise pas la séquence temporelle nativement | 🟢 très faible | 🟡 (SHAP) |
| **LightGBM**    | Features tabulaires, gros volumes | Le plus rapide, faible mémoire, catégoriel natif | Sensible au sur-apprentissage sur petits jeux | 🟢 très faible | 🟡 (SHAP) |
| **CatBoost**    | Features tabulaires catégorielles | Excellent sur catégoriel, peu de tuning | Entraînement plus lent | 🟢 faible | 🟡 |
| **Random Forest**| Features tabulaires          | Baseline robuste, peu de tuning, variance faible | Moins précis que le boosting | 🟢 faible | 🟡 |
| **LSTM**        | Séries temporelles            | Capture les dépendances temporelles moyennes | Entraînement lent, données ++ | 🟡 moyenne | 🔴 |
| **Transformer** | Séries longues, multi-features| Dépendances longues, attention multi-échelle | Gourmand, sur-apprend si peu de data | 🔴 élevée | 🔴 |
| **Reinforcement Learning** | Politique d'exécution/position | Optimise directement le PnL/coût, décision séquentielle | Instable, reward hacking, coûteux à valider | 🟡 variable | 🔴 |

## 2. Recommandation

> **Signal directionnel / probabilité de mouvement** : commencer par
> **LightGBM / XGBoost** sur features soignées — c'est la baseline la plus dure
> à battre en trading, avec inférence sub-milliseconde compatible du live.
>
> **Structure temporelle marquée** (microstructure, saisonnalité intraday) :
> **Transformer** en challenger, **LSTM** en fallback plus léger.
>
> **Exécution / dimensionnement dynamique** (quand/combien exécuter) : **RL**,
> mais uniquement après validation offline stricte et en simulation avant tout
> capital réel.

L'architecture d'inférence est **agnostique du modèle** (interface `Predictor`,
voir `ml/models/registry.py`) : on remplace un LightGBM par un Transformer sans
toucher au reste du pipeline.

## 3. Pipeline complet

```
dataset ─► feature engineering ─► split (train/val/test + OOS)
   │                                     │
   │                             cross-validation (walk-forward, purged/embargo)
   │                                     │
   │                             hyperparam optimisation (Optuna)
   │                                     │
   │                                  training
   │                                     │
   │                                 validation (métriques + backtest)
   │                                     │
   │                        versionning modèle (registry + hash data/features)
   │                                     │
   └────────────────────────────► inférence (service FastAPI / batch)
                                         │
                                     déploiement (canary → prod)
```

### Étapes

1. **Dataset** — assemblé depuis `database/` (barres/ticks) via `python/data`.
2. **Feature engineering** — `ml/features/` : rendements, indicateurs (accélérés
   C++), volatilité réalisée, microstructure. Pas de fuite de futur.
3. **Split** — walk-forward **purgé + embargo** pour séries temporelles
   (jamais de K-fold aléatoire : ça fuit l'information temporelle).
4. **Optimisation** — Optuna, objectif = métrique *économique* (Sharpe OOS),
   pas l'accuracy.
5. **Training / Validation** — métriques ML + **backtest** de la stratégie qui
   consomme le modèle (la vérité terrain est le PnL, pas l'AUC).
6. **Versionning** — chaque modèle est immuable, taggé avec le hash du dataset,
   la version des features et les hyperparamètres (`ml/models/registry.py`).
7. **Inférence / Déploiement** — servi derrière l'interface `Predictor`,
   déploiement canary supervisé par `monitoring/`.

### Anti-fuite (règles non négociables)

- Purge + embargo entre train et test.
- Features calculées **uniquement** avec l'information disponible à `t`.
- Coûts de transaction et slippage inclus dès la validation.
- Le jeu **Out-of-Sample** final n'est touché qu'une seule fois.
