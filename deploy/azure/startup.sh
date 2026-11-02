#!/usr/bin/env bash
# App Service (Linux) startup command for the VISION DEV demo.
# Synthetic data only: the data root is re-seeded on every start in local, ephemeral storage.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export PYTHONPATH="$ROOT:$ROOT/shared/python:$ROOT/modules/proof/src:$ROOT/modules/lion/src:$ROOT/apps/vision/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUTF8=1
export CO_VISION_DATA_ROOT="${CO_VISION_DATA_ROOT:-/tmp/co-vision-dev-data}"
unset CO_VISION_PROOF_DB CO_VISION_PROOF_REFERENCE_DB

rm -rf "$CO_VISION_DATA_ROOT"
python -m tests.e2e.seed "$CO_VISION_DATA_ROOT"

exec python -m streamlit run "$ROOT/apps/vision/src/vision/development_app.py" \
  --server.address 0.0.0.0 \
  --server.port "${PORT:-8000}" \
  --server.headless true \
  --browser.gatherUsageStats false
