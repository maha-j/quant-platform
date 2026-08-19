# Guide d'installation

Installation pas-à-pas de la Quant Platform : environnement Python, cœur C++,
Expert Advisor MQL5, et déploiement Docker/monitoring.

## Sommaire

1. [Prérequis](#1-prérequis)
2. [Récupérer le dépôt](#2-récupérer-le-dépôt)
3. [Environnement Python](#3-environnement-python)
4. [Configuration](#4-configuration)
5. [Vérifier l'installation](#5-vérifier-linstallation)
6. [Cœur C++ (indicateurs + DLL)](#6-cœur-c-indicateurs--dll)
7. [Module Python natif (quant_native)](#7-module-python-natif-quant_native)
8. [Expert Advisor MQL5](#8-expert-advisor-mql5)
9. [Déploiement Docker & monitoring](#9-déploiement-docker--monitoring)
10. [Dépannage](#10-dépannage)

---

## 1. Prérequis

| Outil            | Version         | Nécessaire pour |
|------------------|-----------------|-----------------|
| Python           | 3.11 ou +       | cœur applicatif |
| pip / venv       | récent          | dépendances Python |
| CMake            | 3.20 ou +       | build C++ |
| Compilateur C++  | GCC 12+/Clang 15+ (C++20) | cœur natif |
| Docker + Compose | récent          | déploiement/monitoring |
| MetaTrader 5     | build récent    | exécution live (Windows) |
| Git              | récent          | versionning |

Bibliothèques C++ (optionnelles, pour build complet) : `fmt`, `spdlog`, `Eigen3`,
`pybind11`, `GoogleTest`. Sous Debian/Ubuntu :

```bash
sudo apt-get update
sudo apt-get install -y build-essential cmake git \
    libfmt-dev libspdlog-dev libeigen3-dev pybind11-dev
```

> Le cœur C++ (indicateurs) **compile sans** `fmt`/`spdlog`/`Eigen` : ils ne sont
> liés que s'ils sont présents. `GoogleTest` est récupéré automatiquement par
> CMake (FetchContent) si absent du système.

---

## 2. Récupérer le dépôt

```bash
git clone https://github.com/maha-j/quant-platform.git
cd quant-platform
```

---

## 3. Environnement Python

```bash
# Créer et activer un environnement virtuel
python3 -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate

# Installation cœur + outils de dev (suffit pour les tests et les démos)
pip install -e "./python[dev]"
```

Les dépendances sont déclarées dans [`python/pyproject.toml`](python/pyproject.toml).
Le **cœur** (NumPy, Pandas, Polars, FastAPI, Pydantic, SQLAlchemy, httpx, structlog)
est toujours installé ; les briques lourdes sont des **extras optionnels**, à
l'image des imports guardés dans le code :

| Extra        | Contenu | Installer |
|--------------|---------|-----------|
| `dev`        | pytest, ruff, mypy | `pip install -e "./python[dev]"` |
| `ml`         | scikit-learn, PyTorch, TensorFlow, LightGBM, XGBoost, CatBoost, Optuna | `pip install -e "./python[ml]"` |
| `backtest`   | VectorBT, Backtrader | `pip install -e "./python[backtest]"` |
| `messaging`  | pyzmq (pont ZeroMQ) | `pip install -e "./python[messaging]"` |
| `mt5`        | MetaTrader5 (Windows uniquement) | `pip install -e "./python[mt5]"` |
| `all`        | ml + backtest + messaging + dev (hors `mt5`) | `pip install -e "./python[all]"` |

Le code source vit sous `python/`, `ml/` et `backtests/`. Ajoutez-les au
`PYTHONPATH` pour les exécutions locales :

```bash
export PYTHONPATH="$PWD/python:$PWD"     # Windows : set PYTHONPATH=%CD%\python;%CD%
```

---

## 4. Configuration

La configuration est **typée et validée par Pydantic**
([`python/common/config.py`](python/common/config.py)). Toutes les valeurs se
surchargent par variables d'environnement préfixées `QP_` (séparateur `__` pour
les sous-objets), ou via un fichier `.env`.

Exemple de `.env` :

```dotenv
QP_ENVIRONMENT=dev
QP_DATABASE_URL=postgresql+psycopg://localhost/quant

# Bornes de risque (fractions du capital)
QP_RISK__MAX_DAILY_LOSS_PCT=0.02
QP_RISK__MAX_DRAWDOWN_PCT=0.10
QP_RISK__RISK_PER_TRADE_PCT=0.01
QP_RISK__KELLY_FRACTION=0.5
QP_RISK__AUTO_SHUTDOWN=true

# Messagerie Python ↔ MQL5
QP_MESSAGING__TRANSPORT=zeromq
QP_MESSAGING__SIGNALS_ENDPOINT=tcp://0.0.0.0:5555
QP_MESSAGING__HMAC_SECRET=change-me
QP_MESSAGING__SIGNAL_TTL_SECONDS=30

# Provider MetaTrader 5 (Windows) — identifiants du terminal
QP_MT5__ENABLED=true
QP_MT5__LOGIN=12345678
QP_MT5__PASSWORD=change-me           # via secret manager, jamais commité
QP_MT5__SERVER=Broker-Server
QP_MT5__PATH=                         # vide = auto-détection du terminal
```

Provider de données MetaTrader 5 (nécessite l'extra `mt5` et un terminal MT5) :

```python
from common.config import load_settings
from data.mt5 import MetaTrader5DataSource

ds = MetaTrader5DataSource.connect(load_settings().mt5)   # ouvre le terminal
frame = await ds.fetch("EURUSD", "M15", 500)              # 500 dernières barres
ds.close()
```

Installation de l'extra : `pip install -e "./python[mt5]"` (Windows uniquement).

> **Secrets** : ne jamais committer de secret réel. Le dossier `config/secrets/`
> est ignoré par Git ; n'y placez que des fichiers `*.example`. En production,
> utilisez un gestionnaire de secrets (Vault, AWS SSM…).

---

## 5. Vérifier l'installation

```bash
export PYTHONPATH="$PWD/python:$PWD"

# Lint + tests unitaires
ruff check python ml backtests
pytest tests/unit -q

# Démos bout-en-bout
python python/research/ml_end_to_end.py      # données synthétiques
python python/research/rest_end_to_end.py    # via provider REST (in-process)
```

Résultat attendu : suite de tests verte et un rapport de performance JSON en
sortie des démos (Sharpe, Sortino, Profit Factor, Drawdown…).

Lancer le service d'exécution :

```bash
uvicorn execution.service:app --app-dir python --port 8000
# puis, dans un autre terminal :
curl localhost:8000/health
curl localhost:8000/metrics
```

---

## 6. Cœur C++ (indicateurs + DLL)

```bash
cmake -S cpp -B build -DCMAKE_BUILD_TYPE=Release -DQUANT_BUILD_TESTS=ON
cmake --build build -j
ctest --test-dir build --output-on-failure
```

Artefacts produits dans `build/` :

- `libquant.a` — bibliothèque statique cœur.
- `libquant.so` / `quant.dll` — **bibliothèque exportable** (interopérabilité MQL5).
- `quant_native*.so` — module Python (si `pybind11` est trouvé).

Pour désactiver les tests (ex. hors-ligne, sans GoogleTest) :
`-DQUANT_BUILD_TESTS=OFF`.

---

## 7. Module Python natif (quant_native)

Le module accélère les indicateurs (`ema`, `rsi`, `atr`). Après un build avec
`pybind11`, placez le `.so` généré sur le `PYTHONPATH` :

```bash
cp build/quant_native*.so python/
python -c "import quant_native; print('accélération native OK')"
```

`python/strategies/indicators.py` détecte automatiquement `quant_native` et bascule
dessus ; sinon il utilise l'implémentation Python de repli.

---

## 8. Expert Advisor MQL5

1. Copier les modules dans le répertoire *Data Folder* de MetaTrader 5
   (`Fichier → Ouvrir le dossier de données`) :
   - `mql5/experts/QuantEA.mq5`  → `MQL5/Experts/`
   - `mql5/libraries/*.mqh`      → `MQL5/Include/` (ou à côté de l'EA)
2. Ouvrir `QuantEA.mq5` dans **MetaEditor** et compiler (F7).
3. Dans MT5 : **Outils → Options → Expert Advisors**, autoriser
   `Allow WebRequest`/connexions et ajouter l'adresse du pont
   (ex. `127.0.0.1`).
4. Glisser l'EA sur un graphique et régler les entrées (symboles, host/port du
   pont TCP, bornes de risque, multiplicateurs ATR pour SL/TP/Trailing/BE).

Côté Python, démarrer le pont temps réel :

```bash
# publie les signaux sur ZeroMQ et les relaie en TCP vers l'EA
python -m execution.zmq_tcp_bridge      # depuis python/ sur le PYTHONPATH
```

---

## 9. Déploiement Docker & monitoring

```bash
cd infrastructure/docker
docker compose up --build
```

| Service    | URL/port                | Notes |
|------------|-------------------------|-------|
| API        | http://localhost:8000   | FastAPI + `/metrics` |
| Prometheus | http://localhost:9090   | scrape `execution:8000/metrics` |
| Grafana    | http://localhost:3000   | login `admin` / `admin`, dashboard « Quant Platform » |

Le dashboard et la datasource Prometheus sont **provisionnés automatiquement**
(`monitoring/grafana/provisioning/`).

---

## 10. Dépannage

| Symptôme | Cause probable | Solution |
|----------|----------------|----------|
| `ModuleNotFoundError: common/execution/...` | `PYTHONPATH` non défini | `export PYTHONPATH="$PWD/python:$PWD"` |
| `ModuleNotFoundError: pandas/zmq/structlog` | dépendances non installées | `pip install -e "./python[dev]"` |
| CMake ne trouve pas GoogleTest | pas de réseau pour FetchContent | installer `libgtest-dev` ou `-DQUANT_BUILD_TESTS=OFF` |
| `quant_native` non importé | module natif non compilé/copié | voir [§7](#7-module-python-natif-quant_native) ; sinon repli Python automatique |
| EA ne reçoit pas de signaux | pont non lancé ou host/port erronés | démarrer `execution.zmq_tcp_bridge`, vérifier les entrées de l'EA et le TTL |
| Grafana vide | Prometheus ne scrape pas | vérifier que le service `execution` expose `/metrics` et que Prometheus est up |
