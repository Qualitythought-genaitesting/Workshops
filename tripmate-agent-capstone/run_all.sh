#!/usr/bin/env bash
# TripMate Agent Testing Capstone — one-click runner (macOS / Linux)
# Usage: ./run_all.sh [full|fixed|server|test]
set -u
cd "$(dirname "$0")"
MODE="${1:-full}"
echo "== TripMate Agent Testing Capstone (mode: $MODE) =="

PY=$(command -v python3 || command -v python) || { echo "[ERROR] Python 3.10+ not found"; exit 1; }
[ -d .venv ] || { echo "[1/6] creating venv"; "$PY" -m venv .venv || exit 1; }
# shellcheck disable=SC1091
source .venv/bin/activate
echo "[2/6] installing dependencies"; python -m pip install -q --disable-pip-version-check -r requirements.txt || exit 1

[ -f .env ] && set -a && . ./.env && set +a
[ "$MODE" = "fixed" ] && export DEFECTS_ENABLED=false
export DEFECTS_ENABLED="${DEFECTS_ENABLED:-true}" LLM_PROVIDER="${LLM_PROVIDER:-mock}" RUNS="${RUNS:-5}" PORT="${PORT:-8000}"
export TRIPMATE_URL="http://127.0.0.1:$PORT"
mkdir -p logs data results

if [ "$MODE" != "test" ]; then
  echo "[3/6] starting server on $TRIPMATE_URL (LLM_PROVIDER=$LLM_PROVIDER, DEFECTS_ENABLED=$DEFECTS_ENABLED)"
  for pid in $(pgrep -f "python -m app.server" 2>/dev/null); do kill "$pid" 2>/dev/null; done
  rm -f data/tripmate.db
  nohup python -m app.server > logs/server.out 2>&1 &
  echo $! > logs/server.pid
  for i in $(seq 1 40); do
    python -c "import urllib.request;urllib.request.urlopen('$TRIPMATE_URL/health',timeout=2)" >/dev/null 2>&1 && break
    sleep 1
  done
  echo "       server pid $(cat logs/server.pid)"
fi
open_url() { command -v xdg-open >/dev/null && xdg-open "$1" >/dev/null 2>&1 || command -v open >/dev/null && open "$1" || true; }
if [ "$MODE" = "server" ]; then open_url "$TRIPMATE_URL"; echo "Chat UI: $TRIPMATE_URL  Traces: $TRIPMATE_URL/traces"; exit 0; fi

echo "[4/6] running $RUNS runs x 61 scenarios"; python -m pytest; RC=$?
echo "       pytest exit code $RC (non-zero = some scenarios failed their threshold — expected in the classroom build)"
echo "[5/6] building PRD + Test Plan"; python docs/build_docs.py
echo "[6/6] building execution report"; python reports/build_report.py
echo "----------------------------------------------------------------"
echo " Chat UI:        $TRIPMATE_URL        Trace viewer: $TRIPMATE_URL/traces"
echo " Report:         reports/Test_Execution_Report.html (+ .docx)"
echo " Docs:           docs/PRD_TripMate.docx  docs/Test_Plan_TripMate.docx  docs/Test_Cases_Executed.xlsx"
echo " Stop server:    kill \$(cat logs/server.pid)"
echo "----------------------------------------------------------------"
open_url "reports/Test_Execution_Report.html"; [ "$MODE" != "test" ] && open_url "$TRIPMATE_URL"
exit 0
