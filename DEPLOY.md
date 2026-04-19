# Deploy / Run Guide
<!-- deploy trigger: initial CI test -->


Odoo 19.0 (кастомизированный форк) — запуск через Docker Compose.

## Локальный запуск

### 1. Подготовка
```bash
cp .env.example .env
# отредактируй .env — ADMIN_PASSWD и POSTGRES_PASSWORD уже сгенерированы если делал setup
```

### 2. Старт
```bash
docker compose up -d --build
docker compose logs -f odoo
```

Открой http://localhost:8069 — мастер создания БД.
- **Master password** — из `.env` (`ADMIN_PASSWD`)
- **Database name** — `odoo` (или любое другое)
- **Email / Password** — учётка администратора (первая)

### 3. Остановка
```bash
docker compose down          # остановить, данные сохранены в volumes
docker compose down -v       # снести вместе с БД и filestore (ОСТОРОЖНО)
```

### 4. Пересборка после правки `requirements.txt` / Dockerfile
```bash
docker compose build odoo
docker compose up -d
```

### 5. Dev-режим
В `.env` выставлено:
```
ODOO_WORKERS=0
ODOO_DEV_MODE=reload,qweb,xml
```
Правки в `.py` и XML подхватываются автоматически. Перезапускать контейнер нужно только при:
- правке `requirements.txt`
- установке нового модуля (через UI → Apps)
- правке Dockerfile

### 6. Shell внутрь контейнера
```bash
docker compose exec odoo bash
docker compose exec odoo python3 /opt/odoo/odoo-bin shell -c /etc/odoo/odoo.conf -d odoo
```

---

## Бэкап

### БД
```bash
docker compose exec db pg_dump -U odoo -d odoo -F c -f /tmp/odoo.dump
docker compose cp db:/tmp/odoo.dump ./backups/odoo-$(date +%F).dump
```

### Filestore
```bash
docker run --rm -v odoo_filestore:/data -v $(pwd)/backups:/backup \
  alpine tar czf /backup/filestore-$(date +%F).tgz -C /data .
```

## Восстановление

### БД
```bash
docker compose cp ./backups/odoo-YYYY-MM-DD.dump db:/tmp/odoo.dump
docker compose exec db pg_restore -U odoo -d odoo --clean --if-exists /tmp/odoo.dump
```

### Filestore
```bash
docker run --rm -v odoo_filestore:/data -v $(pwd)/backups:/backup \
  alpine sh -c "cd /data && tar xzf /backup/filestore-YYYY-MM-DD.tgz"
```

---

## Деплой на сервер (Ubuntu 24.04)

### 1. Установить Docker
```bash
sudo apt update && sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list
sudo apt update && sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER  # перелогиниться
```

### 2. Склонировать репо
```bash
git clone <твой-репо-url> /opt/odoo-app
cd /opt/odoo-app
git checkout 19.0   # или setup/docker
```

### 3. Создать `.env` на сервере
Сгенерируй новые пароли (не копируй локальные!):
```bash
python3 -c "import secrets; print('POSTGRES_PASSWORD=' + secrets.token_urlsafe(24))"
python3 -c "import secrets; print('ADMIN_PASSWD=' + secrets.token_urlsafe(32))"
```
Положи значения в `/opt/odoo-app/.env`.

### 4. Запуск
```bash
docker compose up -d --build
```

### 5. Перенос данных с локалки
- Сделай бэкап локально (см. выше)
- `scp backups/*.dump backups/*.tgz user@server:/opt/odoo-app/backups/`
- Восстанови на сервере (см. выше)

---

## TODO: HTTPS через Caddy

Добавить сервис `caddy` в `docker-compose.yml`:
```yaml
caddy:
  image: caddy:2
  restart: unless-stopped
  ports: ["80:80", "443:443"]
  volumes:
    - ./Caddyfile:/etc/caddy/Caddyfile:ro
    - caddy-data:/data
    - caddy-config:/config
  depends_on: [odoo]
```
`Caddyfile`:
```
your-domain.com {
    reverse_proxy /websocket odoo:8072
    reverse_proxy /longpolling/* odoo:8072
    reverse_proxy odoo:8069
}
```
И убрать `ports: 8069/8072` у сервиса `odoo` — пусть будут только внутри docker-сети.

---

## TODO: Автодеплой через GitHub Actions

При push в `19.0` → SSH на сервер → `git pull && docker compose up -d --build`.

Нужно:
1. Сгенерировать SSH-ключ, положить публичный в `~/.ssh/authorized_keys` на сервере.
2. Добавить приватный ключ в GitHub → Settings → Secrets → `DEPLOY_SSH_KEY`, хост в `DEPLOY_HOST`, юзер в `DEPLOY_USER`.
3. Создать `.github/workflows/deploy.yml` примерно такого содержания:
```yaml
name: deploy
on:
  push:
    branches: [19.0]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.DEPLOY_HOST }}
          username: ${{ secrets.DEPLOY_USER }}
          key: ${{ secrets.DEPLOY_SSH_KEY }}
          script: |
            cd /opt/odoo-app
            git pull
            docker compose up -d --build
```

Сделаем, когда будет сервер и доступ.
