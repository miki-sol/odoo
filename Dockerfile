FROM python:3.12-slim-bookworm

ARG TARGETARCH
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    git \
    gnupg \
    gettext-base \
    fonts-dejavu-core \
    fonts-freefont-ttf \
    fonts-inconsolata \
    fonts-font-awesome \
    fonts-noto-core \
    fonts-roboto-unhinted \
    gsfonts \
    libjpeg-dev \
    libldap2-dev \
    libsasl2-dev \
    libssl-dev \
    libxml2-dev \
    libxslt1-dev \
    libpq-dev \
    libpng-dev \
    libtiff-dev \
    libffi-dev \
    libjs-underscore \
    libmagic1 \
    node-less \
    postgresql-client \
    zlib1g-dev \
 && rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    arch="${TARGETARCH:-$(dpkg --print-architecture)}"; \
    url="https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox_0.12.6.1-3.bookworm_${arch}.deb"; \
    curl -fsSLo /tmp/wkhtmltox.deb "$url"; \
    apt-get update; \
    apt-get install -y --no-install-recommends /tmp/wkhtmltox.deb; \
    rm -f /tmp/wkhtmltox.deb; \
    rm -rf /var/lib/apt/lists/*

RUN groupadd -r odoo && useradd -r -g odoo -d /opt/odoo -s /bin/bash odoo

WORKDIR /opt/odoo

COPY requirements.txt /opt/odoo/requirements.txt
RUN pip install --upgrade pip setuptools wheel \
 && pip install -r /opt/odoo/requirements.txt

RUN mkdir -p /var/lib/odoo /etc/odoo \
 && chown -R odoo:odoo /var/lib/odoo /etc/odoo

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER odoo

EXPOSE 8069 8072

ENTRYPOINT ["/entrypoint.sh"]
CMD ["odoo"]
