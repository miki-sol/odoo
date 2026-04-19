#!/usr/bin/env bash
# Pulls latest code. Rebuilds image only if Dockerfile or requirements.txt changed.
# Otherwise just restarts the odoo container (code is bind-mounted).

set -euo pipefail

APP_DIR="/opt/odoo-app"
cd "$APP_DIR"

COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)

OLD_HEAD=$(git rev-parse HEAD)

echo "==> git fetch"
git fetch origin 19.0
NEW_HEAD=$(git rev-parse origin/19.0)

if [ "$OLD_HEAD" = "$NEW_HEAD" ]; then
    echo "==> already up to date ($OLD_HEAD)"
    exit 0
fi

echo "==> updating $OLD_HEAD -> $NEW_HEAD"
git reset --hard origin/19.0

# Decide: rebuild vs restart.
if git diff --name-only "$OLD_HEAD" "$NEW_HEAD" | grep -qE '^(Dockerfile|requirements\.txt|docker/entrypoint\.sh|docker-compose(\.prod)?\.yml|Caddyfile)$'; then
    echo "==> infra/deps changed — rebuilding stack"
    "${COMPOSE[@]}" up -d --build
    docker image prune -f
else
    echo "==> only code changed — restarting odoo (fast path)"
    "${COMPOSE[@]}" restart odoo
fi

echo "==> deploy done"
"${COMPOSE[@]}" ps
