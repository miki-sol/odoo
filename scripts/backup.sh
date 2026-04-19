#!/usr/bin/env bash
# Daily backup of Odoo DB + filestore. Intended for server cron.
# Usage (from /opt/odoo-app):  bash scripts/backup.sh
# Cron example (daily 03:00):
#   0 3 * * * cd /opt/odoo-app && bash scripts/backup.sh >> /var/log/odoo-backup.log 2>&1

set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/odoo}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
DATE="$(date +%F_%H%M)"

mkdir -p "$BACKUP_DIR"
cd "$APP_DIR"

# shellcheck disable=SC1091
set -a; . ./.env; set +a

echo "[$(date -Is)] dumping postgres..."
docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$DB_NAME" -F c \
    > "$BACKUP_DIR/db-$DATE.dump"

echo "[$(date -Is)] archiving filestore..."
FILESTORE_VOL="$(docker compose ps -q odoo | head -1 \
    | xargs -I{} docker inspect {} --format \
    '{{range .Mounts}}{{if eq .Destination "/var/lib/odoo"}}{{.Name}}{{end}}{{end}}')"
docker run --rm -v "$FILESTORE_VOL":/data -v "$BACKUP_DIR":/backup \
    alpine tar czf "/backup/filestore-$DATE.tgz" -C /data .

echo "[$(date -Is)] pruning backups older than ${RETENTION_DAYS}d..."
find "$BACKUP_DIR" -maxdepth 1 -type f \( -name 'db-*.dump' -o -name 'filestore-*.tgz' \) \
    -mtime +"$RETENTION_DAYS" -delete

echo "[$(date -Is)] backup done:"
ls -lh "$BACKUP_DIR" | tail -n +2
