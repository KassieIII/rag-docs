#!/usr/bin/env bash
# First-time deployment helper for a fresh Linux VPS.
# Tested on Debian 12 / Ubuntu 22.04. Run as a user with sudo.
#
# Usage on the server:
#   git clone https://github.com/KassieIII/rag-docs.git
#   cd rag-docs/deploy
#   cp .env.example .env && nano .env       # fill DOMAIN, secrets, basic auth
#   sudo bash deploy.sh
#
# Idempotent: re-running just rebuilds the api image and applies
# migrations. It will not touch your .env or volumes.

set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  echo ".env is missing. Copy .env.example and edit it first." >&2
  exit 1
fi

# Quick sanity check: the example placeholders must be replaced.
if grep -E "(replace-me|replace-with|example\.com)" .env > /dev/null; then
  echo "Your .env still has example placeholders. Replace them first." >&2
  exit 1
fi

# Install Docker if not present.
if ! command -v docker > /dev/null; then
  echo "Installing Docker..."
  curl -fsSL https://get.docker.com | sudo sh
  sudo systemctl enable --now docker
  sudo usermod -aG docker "$USER" || true
fi

# Bring up everything. --build rebuilds the api image from the parent
# directory (the compose context is "..").
echo "Building and starting the stack..."
docker compose --env-file .env -f compose.prod.yml up -d --build

# Apply migrations.
echo "Applying database migrations..."
docker compose --env-file .env -f compose.prod.yml exec -T api alembic upgrade head

# Pull the LLM the first time (idempotent).
. ./.env
echo "Pulling Ollama model: ${OLLAMA_MODEL}"
docker compose --env-file .env -f compose.prod.yml exec -T ollama ollama pull "${OLLAMA_MODEL}"

echo
echo "Done. Verify:"
echo "  curl -fsS https://${DOMAIN}/health"
echo "  curl -fsS https://${DOMAIN}/documents"
echo
echo "To ingest a doc (basic auth required):"
echo "  curl -u admin:<password> -X POST https://${DOMAIN}/ingest \\"
echo "       -H 'content-type: application/json' \\"
echo "       -d '{\"url\":\"https://fastapi.tiangolo.com/\"}'"
