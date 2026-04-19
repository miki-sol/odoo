# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project context

This is a **private fork of Odoo 19.0** (ERP/CRM platform) used as the single source of truth for a student/team project. There is **no intention to pull from upstream**; all customizations — including direct modifications to core modules — live here permanently. The project runs locally via Docker Compose and will be deployed to a self-hosted Ubuntu 24.04 server with the same compose stack.

## Running the project

Docker Compose is the only supported way to run this fork. Do not invoke `odoo-bin` directly on the host.

```bash
docker compose up -d --build      # start odoo + postgres
docker compose logs -f odoo       # follow logs
docker compose down               # stop (keeps data)
docker compose down -v            # DESTRUCTIVE: removes DB + filestore volumes
```

Odoo is on http://localhost:8069. Long-polling / websocket port is 8072. Master password and DB credentials are in `.env` (gitignored, generated per-environment — see `.env.example`).

### Dev-mode behavior

`docker-compose.yml` passes `ODOO_WORKERS=0` and `ODOO_DEV_MODE=reload,qweb,xml` from `.env`, which means:
- Python source changes auto-reload
- QWeb and XML view changes reload without restart
- **Installing a new module, editing `requirements.txt`, or editing the Dockerfile requires `docker compose build odoo` + `up -d`**

### Shell into the container

```bash
docker compose exec odoo bash
docker compose exec odoo python3 /opt/odoo/odoo-bin shell -c /etc/odoo/odoo.conf -d odoo
```

### Running tests for a module

Odoo tests run inside the container using the `-i` (install) or `-u` (update) flags combined with `--test-enable`:

```bash
docker compose exec odoo python3 /opt/odoo/odoo-bin \
    -c /etc/odoo/odoo.conf -d odoo_test \
    --test-enable --stop-after-init -i <module_name>

# run a single test class/method via tags:
#   --test-tags /module_name:TestClassName.test_method
docker compose exec odoo python3 /opt/odoo/odoo-bin \
    -c /etc/odoo/odoo.conf -d odoo_test \
    --test-enable --stop-after-init \
    --test-tags /sale:TestSaleOrder.test_confirm -u sale
```

Use a dedicated `odoo_test` database — tests are destructive.

### Linting

`ruff.toml` at repo root defines the style (auto-generated from Odoo's runbot config, targets Python 3.10):

```bash
ruff check addons/<module>    # lint a specific module
ruff check .                  # full repo (slow — 600+ modules)
```

## Architecture (high-level)

### Layout that matters
- `odoo/` — framework core (ORM, server, modules loader, tools, controllers). Customizations here have broad blast radius.
- `addons/` — ~619 core business modules (accounting, sale, stock, website, hr, etc.). Modifying these is **permitted and expected** in this fork.
- `custom-addons/` — mount point (via `docker-compose.yml`) for **new** modules written from scratch. Prefer this over touching `addons/` when building net-new features.
- `odoo-bin` — CLI entrypoint. Used by the container's `docker/entrypoint.sh`.
- `setup/`, `debian/` — OS packaging. Ignore for day-to-day work; we ship via Docker.

### Module anatomy (`addons/<name>/`)
Each module is a Python package with:
- `__manifest__.py` — declares name, version, dependencies (`depends`), data files, installable flag. **The only reliable place to find a module's dependencies.**
- `models/` — ORM classes inheriting `models.Model` / `models.TransientModel`. Models are identified by `_name` (new) or `_inherit` (extending).
- `views/` — XML definitions for forms/lists/kanbans/menus/actions.
- `security/` — `ir.model.access.csv` + record rules.
- `data/` / `demo/` — XML/CSV seed data, loaded per manifest.
- `static/` — frontend assets (OWL components, SCSS, JS). Registered via manifest `assets` bundles.
- `controllers/` — HTTP routes (`@http.route`).
- `wizard/` — transient models for UI wizards.
- `report/` — QWeb PDF/HTML report definitions.
- `tests/` — tests discovered via `--test-enable` (must be listed in `tests/__init__.py`).

### Key framework concepts to know before editing
- **Models extend via `_inherit`** — most customizations are monkey-patches on existing models, not new classes. Searching for `_inherit = 'sale.order'` shows every module that extends it.
- **Field overrides** happen by re-declaring the field with the same name in an inheriting model. Order depends on module load order (manifest `depends`).
- **Record IDs** are `module.xml_id` strings. `env.ref('sale.group_salesman')` looks up by XML id.
- **Assets bundles** (e.g. `web.assets_backend`, `web.assets_frontend`) are concatenated sets of JS/CSS registered in manifests — frontend changes don't hot-reload reliably; open DevTools with cache disabled, or bump asset version / restart.
- **Migrations**: modules carry `migrations/<version>/` scripts run on update. When modifying a model's schema on an installed DB, update the module (`-u`) to trigger them.

### Data flow
Request → `werkzeug` → `odoo.http` dispatcher → controller → ORM → PostgreSQL. Long-polling / websocket traffic goes to port 8072 (gevent worker) in multi-worker mode; in dev mode (`workers=0`) everything is on 8069.

## Deployment

`DEPLOY.md` is the authoritative guide for:
- Local backup/restore of Postgres dump + filestore tarball
- Ubuntu 24.04 server bootstrap (Docker install, clone, `.env`, `up -d`)
- Caddy + HTTPS reverse proxy (TODO section, not yet configured)
- GitHub Actions auto-deploy over SSH (TODO section)

**When deploying or advising on deploy, read `DEPLOY.md` first** rather than re-deriving commands.

## Conventions for this fork

- **No upstream merges.** Do not suggest pulling from `github.com/odoo/odoo`, do not add `upstream` remote, do not preserve backwards-compat with upstream APIs.
- **New features → `custom-addons/`.** Only edit `addons/<core_module>/` when the change genuinely belongs in that core module (overriding a field/method, fixing a bug).
- **No `.env` in commits.** Passwords are generated per-environment.
- **Dev-mode only.** Production tuning (`workers > 0`, gevent split, memory limits) is not configured yet and is explicitly out of scope for the student-project phase.
