#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
# Explicit overrides allow a fresh environment without deleting an old one.
if [[ -z "${PYTHON:-}" ]]; then
  if command -v python3.13 >/dev/null 2>&1; then PYTHON=python3.13; else PYTHON=python3; fi
fi
DEMO_ENV="${DEMO_ENV:-.venv}"
if [[ ! -x "$DEMO_ENV/bin/python" ]]; then
  "$PYTHON" -m venv "$DEMO_ENV"
fi
# Check the environment actually being used before downloading dependencies.
"$DEMO_ENV/bin/python" app.py --diagnose
"$DEMO_ENV/bin/python" -m pip install -r requirements.txt
"$DEMO_ENV/bin/python" app.py
