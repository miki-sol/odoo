#!/bin/bash
set -e

# Render odoo.conf from template, substituting env vars.
# Source template (read-only mount) lives at /etc/odoo/odoo.conf.tmpl,
# rendered config is written to /etc/odoo/odoo.conf.
if [ -f /etc/odoo/odoo.conf.tmpl ]; then
    envsubst < /etc/odoo/odoo.conf.tmpl > /etc/odoo/odoo.conf
fi

# Wait for Postgres to be reachable before starting Odoo.
if [ -n "$DB_HOST" ]; then
    until pg_isready -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "${DB_USER:-odoo}" >/dev/null 2>&1; do
        echo "waiting for postgres at $DB_HOST:${DB_PORT:-5432}..."
        sleep 1
    done
fi

if [ "$1" = "odoo" ]; then
    shift
    exec python3 /opt/odoo/odoo-bin -c /etc/odoo/odoo.conf "$@"
fi

exec "$@"
