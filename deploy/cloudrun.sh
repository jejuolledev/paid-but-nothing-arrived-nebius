#!/usr/bin/env bash
# Deploy the public demo to Google Cloud Run (owner runs this; Claude does not).
#
#   PROJECT=<gcp-project-id> bash deploy/cloudrun.sh
#
# What it does: builds this folder with Cloud Build (--source), deploys service "paid-but-nothing-arrived"
# with at most ONE instance and zero when idle (so cost stays inside the free tier for a judging demo),
# public (no login, as the rules require), and passes the Token Factory key as an environment variable read
# from .env.local at deploy time. The key never goes into the image or the repository.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${PROJECT:?set PROJECT=<gcp project id>}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-paid-but-nothing-arrived}"
# gcloud on this Mac needs a newer Python than the system one
export CLOUDSDK_PYTHON="${CLOUDSDK_PYTHON:-$HOME/.local/share/uv/python/cpython-3.12.13-macos-aarch64-none/bin/python3.12}"

KEY="$(grep -E '^NEBIUS_API_KEY=' .env.local | head -1 | cut -d= -f2-)"
[ -n "$KEY" ] || { echo "NEBIUS_API_KEY missing in .env.local"; exit 1; }
ls data/precomputed/case*.json >/dev/null 2>&1 || { echo "Run scripts/precompute.py first (recorded example runs)"; exit 1; }
grep -q '"status": "ok"' data/precomputed/case1.json || { echo "data/precomputed/case1.json is not an ok run; rerun precompute"; exit 1; }

ENVF="$(mktemp)"; trap 'rm -f "$ENVF"' EXIT
{
  echo "NEBIUS_API_KEY: \"$KEY\""
  for k in LLM_MODEL LLM_MODEL_INTAKE LLM_MODEL_EXPLAIN LLM_EXTRA_BODY LLM_BASE_URL LLM_VISION_MODEL LLM_VISION_JSON LLM_THINKING_VISION LLM_THINKING_INTAKE; do
    v="$(grep -E "^$k=" .env.local | head -1 | cut -d= -f2- || true)"
    [ -n "$v" ] && printf '%s: %s\n' "$k" "$(python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$v")"
  done
  echo "DEMO_PUBLIC: \"1\""
  # Spending guard for the judging period (the owner's card pays): few live runs per day and per visitor.
  # These counters live in memory, so they reset when Cloud Run starts a new instance; check Token Factory usage weekly.
  echo "DEMO_LIVE_PER_DAY: \"${DEMO_LIVE_PER_DAY:-10}\""
  echo "DEMO_LIVE_PER_IP_HOUR: \"${DEMO_LIVE_PER_IP_HOUR:-4}\""
} > "$ENVF"

gcloud run deploy "$SERVICE" --source . --project "$PROJECT" --region "$REGION" \
  --allow-unauthenticated --min-instances 0 --max-instances 1 --concurrency 20 \
  --cpu 1 --memory 1Gi --timeout 120 --env-vars-file "$ENVF" --quiet

URL="$(gcloud run services describe "$SERVICE" --project "$PROJECT" --region "$REGION" --format 'value(status.url)')"
echo "Deployed: $URL"
curl -fsS "$URL/api/health" && echo
curl -fsS "$URL/api/config" && echo
