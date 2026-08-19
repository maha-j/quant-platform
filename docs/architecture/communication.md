# Communication Python ↔ C++ ↔ MQL5

Décision d'architecture (ADR). Objectif : relier le **cerveau** (Python), les
**calculs critiques** (C++) et l'**exécution broker** (MQL5) avec un transport
adapté à chaque profil de déploiement.

## 1. Les trois liaisons à résoudre

| Liaison            | Nature du flux                                  | Contrainte dominante |
|--------------------|-------------------------------------------------|----------------------|
| Python ↔ C++       | Appels de fonctions (indicateurs, sizing)       | Latence sub-µs, in-process |
| Python ↔ MQL5      | Signaux + télémétrie, cross-process/cross-host  | Robustesse, sécurité |
| C++ ↔ MQL5         | Réutilisation des mêmes calculs dans le terminal| Distribution binaire |

> **Règle structurante :** Python↔C++ n'est *pas* un problème réseau — c'est du
> **binding in-process** (pybind11). Le vrai choix de transport concerne
> Python↔MQL5, car MT5 est un processus tiers, souvent sur un autre hôte (VPS).

## 2. Comparatif des transports (Python ↔ MQL5)

Notation : 🟢 fort · 🟡 moyen · 🔴 faible.

| Transport       | Latence typique | Sécurité (TLS/authn) | Maintenance | Débogage | Scalabilité | Cross-host |
|-----------------|-----------------|----------------------|-------------|----------|-------------|------------|
| **DLL**         | 🟢 ~ns (in-proc) | 🔴 (code natif dans MT5) | 🔴 build/ABI | 🔴 crash = crash MT5 | 🔴 mono-terminal | 🔴 non |
| **Named Pipes** | 🟢 ~10–50 µs    | 🟡 ACL OS            | 🟡          | 🟡        | 🔴 local    | 🔴 non (même hôte) |
| **Shared Memory**| 🟢 ~1 µs        | 🔴 aucune native     | 🔴 sync manuelle | 🔴 difficile | 🔴 local | 🔴 non |
| **Sockets TCP** | 🟢 ~50–200 µs   | 🟡 TLS à ajouter     | 🟢          | 🟢        | 🟡          | 🟢 oui |
| **ZeroMQ**      | 🟢 ~30–100 µs   | 🟡 CurveZMQ          | 🟢 patterns prêts | 🟢    | 🟢 pub/sub  | 🟢 oui |
| **Message Queue** (Redis/RabbitMQ/Kafka) | 🟡 ~1–10 ms | 🟢 authn native | 🟢 | 🟢 | 🟢 persistant | 🟢 oui |
| **REST API**    | 🔴 ~5–50 ms     | 🟢 TLS/OAuth standard | 🟢 | 🟢 | 🟡 requête/réponse | 🟢 oui |
| **gRPC**        | 🟡 ~1–5 ms      | 🟢 mTLS natif        | 🟡 protobuf | 🟡 | 🟢 streaming | 🟢 oui |

Notes MQL5 : MQL5 sait ouvrir des **Sockets TCP natifs** (`SocketCreate`) et
consommer une **DLL** (`#import`). Il ne parle pas nativement ZeroMQ/gRPC/AMQP —
ceux-ci passent soit par une DLL pont, soit par un side-car local qui traduit en
TCP/pipe. C'est un facteur décisif de maintenance.

## 3. Analyse par critère

- **Latence.** Shared Memory > Named Pipes ≈ DLL ≈ ZeroMQ/TCP > MQ > gRPC > REST.
  Pour du signal discret (quelques messages/seconde), l'écart TCP↔SHM est
  invisible ; il ne compte qu'en HFT.
- **Sécurité.** REST/gRPC apportent TLS + auth standard « gratuitement ». DLL et
  Shared Memory n'ont aucune frontière : une DLL boguée fait tomber le terminal.
- **Maintenance.** ZeroMQ et MQ offrent des patterns éprouvés (PUB/SUB, REQ/REP,
  queues durables) et découplent producteur/consommateur. DLL et SHM demandent
  une synchronisation manuelle fragile (ABI, verrous).
- **Débogage.** Tout ce qui est message-oriented et introspectable (TCP, ZeroMQ,
  MQ, REST) se trace ; SHM et DLL sont opaques et provoquent des crashs durs.
- **Scalabilité.** Un bus (ZeroMQ/MQ) sert N terminaux et N stratégies ; DLL/SHM/
  pipes restent mono-hôte.

## 4. Recommandation par profil

| Profil                 | Python ↔ C++ | Python ↔ MQL5                         | Justification |
|------------------------|--------------|---------------------------------------|---------------|
| **Bot personnel**      | pybind11     | **Sockets TCP natifs** (`SocketCreate`) | Zéro dépendance, natif MQL5, cross-host simple, débogable. |
| **Bot VPS**            | pybind11     | **ZeroMQ** via pont léger (PUB/SUB signaux, PUSH/PULL ordres) + TLS/CurveZMQ | Découplage, reconnexion, un broker Python → N terminaux. |
| **Bot institutionnel** | pybind11     | **Message Queue durable** (Kafka/RabbitMQ) + **gRPC/mTLS** pour le contrôle | Persistance, rejouabilité, audit, authz forte, multi-desk. |
| **HFT**                | pybind11     | **Shared Memory** (co-localisé) + DLL native, fallback Named Pipes | La microseconde prime ; co-location supprime le réseau. MQL5 rarement le bon terminal en vrai HFT. |

## 5. Architecture retenue par défaut (VPS / institutionnel léger)

```
                 pybind11 (in-process, ns)
   Python  ◄──────────────────────────────►  C++ (indicateurs, sizing)
     │
     │  ZeroMQ  PUB  "signals"   (TLS/Curve)      ┌──────────────┐
     ├───────────────────────────────────────────►│  Pont / EA   │
     │  ZeroMQ  PULL "orders/fills" (télémétrie)   │  MQL5 (MT5)  │
     └───────────────────────────────◄────────────┴──────────────┘
```

- **Contrat de message** : JSON versionné validé par Pydantic côté Python et par
  un parseur dédié côté MQL5 (`SignalReceiver.mqh`). Champs : `schema_version`,
  `symbol`, `side`, `confidence`, `sl`, `tp`, `risk_pct`, `ttl`, `signature`.
- **Idempotence** : chaque signal porte un `signal_id` ; l'EA déduplique.
- **Sécurité** : chiffrement du canal + HMAC applicatif sur le payload.
- **Résilience** : heartbeat + TTL ; au-delà du TTL, l'EA ignore le signal.

Le même code C++ (`libquant`) est compilé en **DLL exportable** pour être
réutilisé directement dans MT5 quand la co-location l'exige (chemin HFT).
