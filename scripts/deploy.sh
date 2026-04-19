#!/usr/bin/env bash
# Idempotent deploy: pull latest code, rebuild image if infra changed,
# install/update any changed Odoo modules (in custom-addons/ or addons/),
# restart the server. Called both manually and by GitHub Actions.

set -euo pipefail

APP_DIR="/opt/odoo-app"
cd "$APP_DIR"

COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)

# Load DB creds for psql queries.
set -a; . ./.env; set +a

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

DIFF_FILES=$(git diff --name-only "$OLD_HEAD" "$NEW_HEAD")

# 1. Rebuild image if infra files changed.
INFRA_CHANGED=0
if echo "$DIFF_FILES" | grep -qE '^(Dockerfile|requirements\.txt|docker/entrypoint\.sh|docker-compose(\.prod)?\.yml|Caddyfile)$'; then
    INFRA_CHANGED=1
fi

if [ "$INFRA_CHANGED" = 1 ]; then
    echo "==> infra changed — rebuilding stack"
    "${COMPOSE[@]}" up -d --build
    docker image prune -f
else
    echo "==> infra unchanged — container running as is"
    "${COMPOSE[@]}" up -d
fi

# 2. Determine which Odoo modules changed (custom-addons/* and addons/*).
CHANGED_MODULES=$(echo "$DIFF_FILES" \
    | awk -F/ '($1=="custom-addons" || $1=="addons") && NF>=2 {print $2}' \
    | sort -u \
    | grep -vE '^(\.gitkeep|__pycache__)$' || true)

if [ -z "$CHANGED_MODULES" ]; then
    echo "==> no module changes — skipping install/update"
    echo "==> deploy done"
    "${COMPOSE[@]}" ps
    exit 0
fi

echo "==> changed modules:"
echo "$CHANGED_MODULES" | sed 's/^/    - /'

# 3. Ask the DB which of those are already installed.
SQL_LIST=$(echo "$CHANGED_MODULES" | awk 'BEGIN{ORS=""} {if(NR>1) printf ","; printf "'"'"'%s'"'"'", $0}')
INSTALLED=$("${COMPOSE[@]}" exec -T db psql -U "$POSTGRES_USER" -d "$DB_NAME" -tA \
    -c "SELECT name FROM ir_module_module WHERE state='installed' AND name IN ($SQL_LIST)" \
    | sed '/^$/d' | sort -u || true)

# Modules to INSTALL: new custom-addons only. We never auto-install core addons
# the user hasn't opted into — only update them if already installed.
NEW_CUSTOM=$(echo "$DIFF_FILES" \
    | awk -F/ '$1=="custom-addons" && NF>=2 {print $2}' \
    | sort -u | grep -vE '^(\.gitkeep|__pycache__)$' || true)
TO_INSTALL=$(comm -23 <(echo "$NEW_CUSTOM") <(echo "$INSTALLED") | paste -sd ',' -)
TO_UPDATE=$(echo "$INSTALLED" | paste -sd ',' -)

# 4. Run odoo-bin in a one-shot container so the live server doesn't fight
#    for the module lock. Bring it back up after.
if [ -n "$TO_UPDATE" ] || [ -n "$TO_INSTALL" ]; then
    echo "==> stopping odoo for module migration"
    "${COMPOSE[@]}" stop odoo

    if [ -n "$TO_UPDATE" ]; then
        echo "==> updating modules: $TO_UPDATE"
        "${COMPOSE[@]}" run --rm odoo odoo -u "$TO_UPDATE" --stop-after-init
    fi
    if [ -n "$TO_INSTALL" ]; then
        echo "==> installing modules: $TO_INSTALL"
        "${COMPOSE[@]}" run --rm odoo odoo -i "$TO_INSTALL" --stop-after-init
    fi

    echo "==> starting odoo"
    "${COMPOSE[@]}" start odoo
else
    echo "==> no installed modules matched the diff — nothing to do"
fi

echo "==> deploy done"
"${COMPOSE[@]}" ps
