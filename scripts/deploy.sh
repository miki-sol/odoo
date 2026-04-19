#!/usr/bin/env bash
# Pulls latest code and rebuilds the stack on the server.
# Run manually:  cd /opt/odoo-app && bash scripts/deploy.sh
# Invoked automatically by .github/workflows/deploy.yml over SSH.

set -euo pipefail

APP_DIR="/opt/odoo-app"
cd "$APP_DIR"

echo "==> git pull"
git fetch origin
git reset --hard origin/19.0

echo "==> docker compose up (rebuild if needed)"
docker compose pull db || true
docker compose up -d --build

echo "==> prune dangling images"
docker image prune -f

echo "==> deploy done"
docker compose ps
