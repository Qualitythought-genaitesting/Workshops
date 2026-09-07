#!/usr/bin/env bash
# Developer helper (Linux/macOS): restart the TripMate server in the background.
cd "$(dirname "$0")/.."
for pid in $(pgrep -f "python3 -m app.server"); do kill "$pid" 2>/dev/null; done
sleep 1
rm -f data/tripmate.db logs/*.log
mkdir -p logs
setsid nohup env TRIPMATE_TODAY="${TRIPMATE_TODAY:-}" python3 -m app.server > logs/server.out 2>&1 &
for i in $(seq 1 20); do curl -s localhost:8000/health >/dev/null && break; sleep 0.5; done
curl -s localhost:8000/health | head -c 120; echo
