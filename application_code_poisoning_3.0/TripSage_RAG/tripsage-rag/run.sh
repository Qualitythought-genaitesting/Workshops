#!/usr/bin/env bash
# TripSage RAG - one-click launcher (Linux / macOS)
cd "$(dirname "$0")"
PY="$(command -v python3 || command -v python)"
if [ -z "$PY" ]; then
  echo "Python 3 is required but was not found."
  echo "Install it from https://www.python.org/downloads/ then run this again."
  read -p "Press Enter to exit..." _; exit 1
fi
echo "Starting TripSage RAG... your browser will open automatically."
echo "If it does not, open the URL printed below. Press Ctrl+C to stop."
"$PY" app.py
