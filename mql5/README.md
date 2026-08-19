# mql5/

Code MetaTrader 5 (MQL5) — connectivité et exécution côté terminal broker.

- `experts/` — Expert Advisors (robots de trading exécutés dans le terminal).
- `indicators/` — indicateurs custom.
- `libraries/` — code MQL5 réutilisable (`.mqh`) partagé entre EA et indicateurs.

**Règle :** isolé du reste du dépôt ; communique avec `python/execution` via un
pont défini (socket / fichier / ZeroMQ), jamais par appel direct.
