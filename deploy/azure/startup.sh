#!/usr/bin/env bash
# App Service (Linux) startup command for the VISION DEV demo.
# Synthetic data only: the data root is re-seeded on every start in local, ephemeral storage.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export PYTHONPATH="$ROOT:$ROOT/shared/python:$ROOT/modules/proof/src:$ROOT/modules/lion/src:$ROOT/apps/vision/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUTF8=1
DATA_ROOT=/tmp/co-vision-dev-data
if [ "${CO_VISION_DATA_ROOT:-$DATA_ROOT}" != "$DATA_ROOT" ]; then
  echo "CO_VISION_DATA_ROOT must remain the disposable synthetic DEV directory." >&2
  exit 1
fi
export CO_VISION_DATA_ROOT="$DATA_ROOT"
export VISION_AUTH_MODE=temporary
: "${VISION_AUTH_COOKIE_SECRET:?Set the temporary auth signing key outside Git}"
: "${VISION_AUTH_PUBLIC_ORIGIN:?Set the approved HTTPS origin}"
: "${VISION_TEMP_USERS_JSON:?Configure synthetic test users outside Git}"
: "${VISION_AUTHZ_ASSIGNMENTS_JSON:?Configure explicit role scopes outside Git}"
unset CO_VISION_PROOF_DB CO_VISION_PROOF_REFERENCE_DB

rm -rf -- "$DATA_ROOT"
python -m tests.e2e.seed "$CO_VISION_DATA_ROOT"

exec python -m uvicorn vision.asgi_app:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers 1
