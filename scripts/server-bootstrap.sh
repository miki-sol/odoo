#!/usr/bin/env bash
# Run once on a fresh Ubuntu 24.04 server as root.
# Installs Docker, configures firewall, clones repo, generates .env.
# Usage:  bash server-bootstrap.sh

set -euo pipefail

REPO_URL="https://github.com/miki-sol/odoo.git"
APP_DIR="/opt/odoo-app"
BRANCH="19.0"

echo "==> apt update & base tools"
apt-get update
apt-get install -y ca-certificates curl git ufw python3 python3-venv

echo "==> install Docker"
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo "==> firewall (ssh + http/https for Caddy)"
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp
ufw --force enable

echo "==> clone repo"
if [ ! -d "$APP_DIR/.git" ]; then
    git clone --depth=1 --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
else
    git -C "$APP_DIR" fetch origin "$BRANCH"
    git -C "$APP_DIR" checkout "$BRANCH"
    git -C "$APP_DIR" pull --ff-only origin "$BRANCH"
fi

echo "==> generate .env (only if missing)"
if [ ! -f "$APP_DIR/.env" ]; then
    POSTGRES_PW=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
    ADMIN_PW=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    cat > "$APP_DIR/.env" <<EOF
POSTGRES_USER=odoo
POSTGRES_PASSWORD=${POSTGRES_PW}
DB_NAME=odoo
ADMIN_PASSWD=${ADMIN_PW}
ODOO_WORKERS=0
ODOO_DEV_MODE=reload,qweb,xml
EOF
    chmod 600 "$APP_DIR/.env"
    echo "    .env created at $APP_DIR/.env"
    echo "    ADMIN_PASSWD=${ADMIN_PW}"
    echo "    (save it — master password for Odoo DB manager)"
else
    echo "    .env already exists — keeping it"
fi

echo "==> build & start stack (with Caddy for HTTPS)"
cd "$APP_DIR"
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

echo ""
echo "==> done"
echo "    Odoo will be available at https://185-197-251-184.sslip.io in ~1-2 min"
echo "    (Caddy needs a moment to obtain Let's Encrypt cert on first run)"
echo "    Logs:  cd $APP_DIR && docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f"
