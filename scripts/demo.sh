#!/usr/bin/env bash
# Demo script for rag-docs.
#
# Walks an end-to-end happy path against a running stack (default:
# http://localhost:8000) so that:
#   - reviewers can copy-paste a single command instead of reading the
#     OpenAPI page
#   - the asciinema recording in the README is reproducible
#
# Usage:
#   ./scripts/demo.sh                      # against localhost:8000
#   BASE_URL=http://api.example.com ./scripts/demo.sh
#   RECORD=1 ./scripts/demo.sh             # wraps the run in asciinema

set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
DEMO_URL="${DEMO_URL:-https://raw.githubusercontent.com/tiangolo/fastapi/master/docs/en/docs/tutorial/first-steps.md}"
QUESTION="${QUESTION:-How do I declare a path parameter?}"

if [[ "${RECORD:-0}" == "1" ]]; then
  exec asciinema rec -c "$0" --idle-time-limit 2 --title "rag-docs demo" assets/demo.cast
fi

bold()  { printf "\n\033[1;36m▶ %s\033[0m\n" "$*"; }
quiet() { printf "  %s\n" "$*"; }

bold "1. /health — DB + embedder + LLM should all be true"
curl -fsS "${BASE_URL}/health" | python3 -m json.tool

bold "2. /ingest — chunk + embed a Markdown doc into pgvector"
curl -fsS -X POST "${BASE_URL}/ingest" \
  -H "Content-Type: application/json" \
  -d "{\"url\":\"${DEMO_URL}\"}" | python3 -m json.tool

bold "3. /ask — citation-grounded answer (single JSON response)"
curl -fsS -X POST "${BASE_URL}/ask" \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"${QUESTION}\",\"top_k\":5}" | python3 -m json.tool

bold "4. /ask/stream — same answer, streamed token-by-token over SSE"
quiet "(citations come up front, then tokens, then 'done')"
curl -fsSN -X POST "${BASE_URL}/ask/stream" \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"${QUESTION}\",\"top_k\":5}"

bold "5. /metrics — Prometheus exposition (top 12 lines)"
curl -fsS "${BASE_URL}/metrics" | grep -E "^rag_" | head -n 12

bold "Done."
