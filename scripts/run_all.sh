#!/usr/bin/env bash
# Démarre toute la pile locale en une commande : service FastAPI + pont
# ZeroMQ→TCP + simulateur de trading démo.
#
#   scripts/run_all.sh            # service + pont, lance la démo, reste actif (Ctrl-C pour tout arrêter)
#   scripts/run_all.sh --once     # lance la démo puis arrête tout (test rapide)
#   scripts/run_all.sh --no-demo  # service + pont seulement
#
# Le pont nécessite pyzmq (extra "messaging") ; s'il est absent, il est ignoré
# proprement et le reste démarre quand même.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$ROOT/python:$ROOT"
HOST="${QP_HOST:-127.0.0.1}"
PORT="${QP_PORT:-8000}"
LOGDIR="$ROOT/logs"
mkdir -p "$LOGDIR"

ONCE=0
RUN_DEMO=1
for arg in "$@"; do
  case "$arg" in
    --once) ONCE=1 ;;
    --no-demo) RUN_DEMO=0 ;;
    *) echo "argument inconnu: $arg" >&2; exit 2 ;;
  esac
done

PIDS=()
cleanup() {
  echo; echo "→ arrêt des services…"
  for p in "${PIDS[@]:-}"; do kill "$p" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

PY="$(command -v python3 || command -v python)"

# 1) Service FastAPI ---------------------------------------------------------
if curl -sf "http://$HOST:$PORT/health" >/dev/null 2>&1; then
  echo "⚠ un service répond déjà sur $HOST:$PORT — je le réutilise."
else
  echo "→ démarrage du service ($HOST:$PORT)…"
  "$PY" -m uvicorn execution.service:app --app-dir "$ROOT/python" \
        --host "$HOST" --port "$PORT" > "$LOGDIR/service.log" 2>&1 &
  PIDS+=($!)
  for _ in $(seq 1 30); do
    curl -sf "http://$HOST:$PORT/health" >/dev/null 2>&1 && break
    sleep 1
  done
  curl -sf "http://$HOST:$PORT/health" >/dev/null 2>&1 \
    && echo "  ✓ service prêt (voir $LOGDIR/service.log)" \
    || { echo "  ✗ le service n'a pas démarré"; exit 1; }
fi

# 2) Pont ZeroMQ → TCP (optionnel) -------------------------------------------
if "$PY" -c "import zmq" >/dev/null 2>&1; then
  echo "→ démarrage du pont ZeroMQ→TCP (port 5560)…"
  "$PY" -m execution.zmq_tcp_bridge > "$LOGDIR/bridge.log" 2>&1 &
  PIDS+=($!)
  echo "  ✓ pont actif (voir $LOGDIR/bridge.log)"
else
  echo "⚠ pyzmq absent — pont non démarré (pip install -e ./python[messaging])"
fi

# 3) Simulateur de trading démo ---------------------------------------------
if [ "$RUN_DEMO" -eq 1 ]; then
  echo "→ lancement du simulateur de trading démo…"; echo
  "$PY" "$ROOT/python/research/paper_trading_demo.py"
fi

# 4) Rester actif (sauf --once) ---------------------------------------------
if [ "$ONCE" -eq 1 ]; then
  echo; echo "→ mode --once : arrêt."
  exit 0
fi

echo
echo "Pile active :"
echo "  • API      : http://$HOST:$PORT (/docs, /metrics)"
"$PY" -c "import zmq" >/dev/null 2>&1 && echo "  • pont TCP : $HOST:5560 (pour l'EA MQL5)"
echo "Ctrl-C pour tout arrêter."
wait
