# TRAC container image. Build:  docker build -t trac .
# Content (guides, controls, platforms) is baked into the image from the content/ folder:
# edit the files, rebuild, redeploy, and the start-up script syncs the changes into the site.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    DJANGO_SETTINGS_MODULE=config.settings.prod \
    APP_DIR=/app \
    PORT=8000

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/venv

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Styling files are prepared at build time. The key here is only for this build step.
RUN SECRET_KEY=build-only-not-secret python manage.py collectstatic --noinput \
    && chmod +x docker/start.sh \
    && useradd --system --uid 10001 --home /app trac \
    && chown -R trac /app

USER 10001
EXPOSE 8000
CMD ["/app/docker/start.sh"]
