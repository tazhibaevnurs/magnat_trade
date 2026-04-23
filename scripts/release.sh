#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[release] step 1/6: backup database"
"$ROOT_DIR/scripts/backup-before-deploy.sh"

echo "[release] step 2/6: pull latest code"
git pull --ff-only

echo "[release] step 3/6: build images"
docker compose build web celery celery-beat

echo "[release] step 4/6: run migrations"
docker compose run --rm web python manage.py migrate --noinput

echo "[release] step 5/6: collect static"
docker compose run --rm web python manage.py collectstatic --noinput

echo "[release] step 6/6: start application stack"
docker compose up -d db redis web celery celery-beat

echo "[release] smoke checks"
docker compose exec web python manage.py check
docker compose exec web python manage.py showmigrations --plan | sed -n '1,120p'

echo "[release] success"
