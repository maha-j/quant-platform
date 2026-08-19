# Quant Platform

[![CI](https://github.com/maha-j/quant-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/maha-j/quant-platform/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/maha-j/quant-platform/branch/main/graph/badge.svg)](https://codecov.io/gh/maha-j/quant-platform)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](python/pyproject.toml)

Plateforme de trading quantitatif de type *hedge fund*, organisée par **domaine
technique**. Chaque dossier racine est autonome, possède une frontière claire et
un `README.md` décrivant son rôle, ses entrées/sorties et ses règles.

- **Python** — le cerveau : données, IA/ML/DL, signaux, risque, exécution, reporting.
- **C++20** — uniquement les traitements critiques (indicateurs, basse latence, DLL exportable).
- **MQL5** — Expert Advisor MetaTrader 5 modulaire (exécution côté broker).

> **Principe directeur :** une préoccupation = un dossier racine. Aucun code
> métier n'est dupliqué entre langages ; les frontières entre `python/`, `cpp/`
> et `mql5/` sont explicites.

## Sommaire

- [Fonctionnalités](#fonctionnalités)
- [Pile technique](#pile-technique)
- [Architecture](#architecture)
- [Structure du dépôt](#structure-du-dépôt)
- [Démarrage rapide](#démarrage-rapide)
- [Exécuter les tests & les démos](#exécuter-les-tests--les-démos)
- [Build C++](#build-c)
- [Déploiement Docker & monitoring](#déploiement-docker--monitoring)
- [État & feuille de route](#état--feuille-de-route)

## Fonctionnalités

**Cerveau Python (SOLID + Pydantic)**
- Récupération de données asynchrone (`asyncio`), providers interchangeables (CSV, REST, MetaTrader 5).
- Indicateurs techniques (ATR / EMA / RSI) avec accélération native C++ optionnelle.
- Génération de signaux via interface `Strategy` extensible.
- **Moteur de risque institutionnel** : Max Daily/Weekly Loss, Max Drawdown, Risk per Trade,
  Kelly, ATR sizing, filtres (spread, slippage, volatilité, liquidité, corrélation, news,
  exposition), Equity Protection, Auto-Shutdown — **toutes les valeurs configurables**.
- **Backtesting** : Walk-Forward purgé, Monte-Carlo, optimisation grille + algorithme
  génétique ; métriques exportables (Sharpe, Sortino, Profit Factor, Recovery, Ulcer,
  Expectancy, Drawdown…).
- **Pipeline ML agnostique du modèle** : feature engineering sans fuite de futur,
  validation walk-forward + embargo, versionning des modèles, inférence.
- Service d'exécution **FastAPI** avec signature HMAC/TTL et exposition **Prometheus** `/metrics`.

**Cœur C++20 (RAII, sans pointeurs bruts)**
- Indicateurs haute performance (`std::span`/`std::vector`), un seul parcours O(n).
- Compilé en lib statique, **DLL/so exportable** (interop MQL5) et module Python (pybind11).

**Expert Advisor MQL5 (modulaire, volontairement fin)**
- Modules séparés : `Logger`, `SignalReceiver` (TCP), `RiskManager`, `TradeManager`.
- SL / TP / Trailing Stop / Break Even, multi-symboles, multi-timeframes, gestion d'erreurs.

## Pile technique

| Domaine        | Technologies |
|----------------|--------------|
| Langages       | Python 3.11+, C++20, MQL5 |
| Data / calcul  | NumPy, Pandas, Polars |
| ML / DL        | scikit-learn, PyTorch, TensorFlow, LightGBM, XGBoost, CatBoost, Optuna |
| Backtesting    | moteur maison, VectorBT, Backtrader |
| API / modèles  | FastAPI, Pydantic, SQLAlchemy |
| Messagerie     | ZeroMQ (PUB/SUB), TCP natif MQL5 |
| C++            | CMake, GoogleTest, fmt, spdlog, Eigen, pybind11 |
| Infra / obs    | Docker, Docker Compose, Prometheus, Grafana, GitHub Actions |

## Architecture

Deux décisions clés sont documentées en détail :

- **Communication Python ↔ C++ ↔ MQL5** — [docs/architecture/communication.md](docs/architecture/communication.md)
  (comparatif DLL / TCP / REST / gRPC / ZeroMQ / Named Pipes / Shared Memory / MQ
  sur latence, sécurité, maintenance, débogage, scalabilité ; recommandation par profil).
- **Modèles IA** — [docs/architecture/ai-models.md](docs/architecture/ai-models.md)
  (LSTM / Transformer / XGBoost / LightGBM / CatBoost / Random Forest / RL + pipeline complet).

**Recommandation de transport par profil** (voir la doc pour le détail) :

| Profil                 | Python ↔ C++ | Python ↔ MQL5 |
|------------------------|--------------|---------------|
| Bot personnel          | pybind11     | Sockets TCP natifs |
| Bot VPS                | pybind11     | ZeroMQ (PUB/SUB) + side-car TCP |
| Bot institutionnel     | pybind11     | Message Queue durable + gRPC/mTLS |
| Haute fréquence (HFT)  | pybind11     | Shared Memory / DLL co-localisée |

### Flux de données

```
data providers ──► python/data ──► database ──► ml/features ──► ml/models
                                       │                            │
                                       ▼                            ▼
                                  backtests ◄────────────── python/strategies
                                       │                            │
                                       ▼                            ▼
                              python/execution ──► cpp (ordres) ──► broker / mql5
                                       │
                                       ▼
                              logs + monitoring
```

### Chaîne temps réel Python → MQL5

```
SignalPublisher (ZeroMQ PUB) ──► [side-car SUB + serveur TCP] ──► EA MQL5 (SocketConnect)
```

## Structure du dépôt

| Dossier            | Rôle                                                                 | Versionné |
|--------------------|----------------------------------------------------------------------|-----------|
| `python/`          | Recherche, pipelines de données, logique de stratégie, exécution     | oui       |
| `cpp/`             | Composants basse latence (indicateurs critiques, DLL exportable)     | oui       |
| `mql5/`            | Expert Advisor & indicateurs MetaTrader 5                            | oui       |
| `config/`          | Configuration déclarative (environnements, paramètres stratégies)    | oui\*     |
| `docs/`            | Documentation d'architecture, stratégies et procédures d'exploitation| oui       |
| `infrastructure/`  | Infrastructure as Code (Terraform, Docker, Kubernetes, Ansible)      | oui       |
| `database/`        | Migrations, schémas et jeux de données de référence                  | oui       |
| `backtests/`       | Moteur de backtest, scénarios et résultats                           | oui\*     |
| `ml/`              | Features, modèles, entraînement et notebooks de recherche            | oui       |
| `logs/`            | Sorties de logs au runtime                                           | non       |
| `monitoring/`      | Prometheus, dashboards Grafana, règles d'alerte                      | oui       |
| `tests/`           | Suites de tests (unitaires, intégration, performance)                | oui       |
| `scripts/`         | Scripts d'exploitation (déploiement, données, maintenance)           | oui       |
| `cicd/`            | Pipelines d'intégration et de déploiement continus                   | oui       |

\* Le contenu sensible ou volumineux (`config/secrets/`, `backtests/results/`,
`logs/`) est ignoré par Git ; seul le dossier est conservé via `.gitkeep`.

Chaque dossier racine contient son propre `README.md` détaillant son rôle et ses règles.

## Démarrage rapide

> Guide d'installation pas-à-pas complet : **[INSTALL.md](INSTALL.md)**.

```bash
# 1. Environnement Python (cœur + dev ; ML/backtest/messaging = extras optionnels)
python3 -m venv .venv && source .venv/bin/activate
pip install -e "./python[dev]"          # tout : "./python[all]"

# 2. Lancer la suite de tests
export PYTHONPATH="$PWD/python:$PWD"
pytest tests/unit -q

# 3. Démo ML bout-en-bout (données synthétiques)
python python/research/ml_end_to_end.py

# 4. Démo ML via provider REST (in-process, sans réseau)
python python/research/rest_end_to_end.py
```

## Exécuter les tests & les démos

```bash
export PYTHONPATH="$PWD/python:$PWD"

pytest tests/unit -q                         # tous les tests unitaires Python
ruff check python ml backtests               # lint
python python/research/ml_end_to_end.py      # data synthétique → features → train → backtest
python python/research/rest_end_to_end.py    # même chaîne via un provider REST FastAPI
```

Le service d'exécution et ses métriques :

```bash
uvicorn execution.service:app --app-dir python --port 8000
curl localhost:8000/health
curl -X POST localhost:8000/signals -H 'content-type: application/json' \
     -d '{"symbol":"EURUSD","side":"buy","confidence":0.8,"atr":0.001}'
curl localhost:8000/metrics          # exposition Prometheus
```

## Build C++

```bash
cmake -S cpp -B build -DCMAKE_BUILD_TYPE=Release -DQUANT_BUILD_TESTS=ON
cmake --build build -j
ctest --test-dir build --output-on-failure
```

Produit : `libquant.a` (statique), `libquant.so`/`.dll` (exportable pour MQL5) et,
si `pybind11` est présent, le module Python `quant_native` (accélère les indicateurs).

## Déploiement Docker & monitoring

```bash
cd infrastructure/docker
docker compose up --build
```

Services exposés :

| Service           | Port  | Rôle |
|-------------------|-------|------|
| execution (API)   | 8000  | FastAPI + `/metrics` |
| ZeroMQ signaux    | 5555  | PUB des signaux |
| ZeroMQ télémétrie | 5556  | PULL ordres/fills |
| side-car TCP      | 5560  | relais vers l'EA MQL5 |
| Prometheus        | 9090  | scraping des métriques |
| Grafana           | 3000  | dashboard « Quant Platform » (pré-provisionné) |

Le dashboard Grafana (`monitoring/grafana/dashboards/quant-overview.json`) est
provisionné automatiquement et connecté à Prometheus qui scrape `execution:8000/metrics`.

## État & feuille de route

**Vérifié :** suite Python **17/17** verte, lint propre, cœur C++ compilé
(CMake → `libquant.a` + `libquant.so`) et indicateurs vérifiés, démos ML
synthétique et REST exécutées.

**À brancher pour la production :** provider de données réel (broker/vendor),
pont ZeroMQ en conditions live, compilation du module `quant_native` et de l'EA
MQL5 dans MetaTrader 5, règles d'alerte Alertmanager.

## Licence

Distribué sous licence **MIT** — voir [LICENSE](LICENSE). Logiciel fourni « en
l'état », sans garantie. Le trading comporte un risque de perte en capital ;
utilisez à vos propres risques.
