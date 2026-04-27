# Полное руководство по деплою (Production Runbook)

## 1. Текущая схема продакшена

- База данных: PostgreSQL
- Кэш/очереди: Redis
- Приложение: Django + Gunicorn (`web`)
- Фоновые задачи: Celery (`celery`) + Celery Beat (`celery-beat`)
- Интеграция с 1С: через `ONEC_API_BASE_URL` и задачи синхронизации

## 2. Что делают скрипты

### `scripts/backup-before-deploy.sh`

Скрипт делает резервную копию PostgreSQL перед релизом:

1. Поднимает сервис `db`:
   - `docker compose up -d db`
2. Ждет готовности Postgres:
   - `pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"`
   - до 30 попыток с паузой 2 секунды
3. Делает backup:
   - `pg_dump -Fc`
4. Сохраняет файл:
   - `/opt/magnat_trade/backups/postgres_YYYY-MM-DD_HH-MM-SS.dump`

Итог: перед каждым релизом есть актуальный backup для rollback.

### `scripts/release.sh`

Скрипт выполняет безопасный релиз:

1. `backup-before-deploy.sh`
2. `git pull --ff-only`
3. `docker compose build web celery celery-beat`
4. `docker compose run --rm web python manage.py migrate --noinput`
5. `docker compose up -d db redis web celery celery-beat`
6. `docker compose exec web python manage.py collectstatic --noinput`
7. Smoke-check:
   - `python manage.py check`
   - `python manage.py showmigrations --plan`

Итог: обновление кода + миграции + сборка + запуск сервисов + базовая проверка.

## 3. Обязательные проверки до деплоя

Выполнять в `/opt/magnat_trade`:

```bash
grep -E "^(DATABASE_URL|POSTGRES_DB|POSTGRES_USER|POSTGRES_PASSWORD|ONEC_API_BASE_URL|REDIS_URL|CELERY_BROKER_URL|CELERY_RESULT_BACKEND)=" .env
docker compose ps
docker compose exec db sh -lc 'export PGPASSWORD="$POSTGRES_PASSWORD"; pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

Проверить, что пароль в `DATABASE_URL` совпадает с `POSTGRES_PASSWORD`.

## 4. Стандартный деплой (основной сценарий)

```bash
cd /opt/magnat_trade
bash scripts/release.sh
```

После релиза обновить каталог из 1С:

```bash
docker compose exec web python manage.py sync_onec
docker compose exec web python manage.py shell -c "from products.models import Category, Product; from shop.models import Category as ShopCategory; print('products categories=', Category.objects.count(), 'shop categories=', ShopCategory.objects.count(), 'products=', Product.objects.count())"
```

## 5. Проверка, что всё работает

```bash
docker compose ps
docker compose logs --tail=120 web
docker compose logs --tail=120 celery
docker compose logs --tail=120 celery-beat
docker compose exec web python manage.py shell -c "from django.conf import settings; print(settings.DATABASES['default']['ENGINE'])"
```

Ожидается:
- контейнеры `Up`,
- `ENGINE = django.db.backends.postgresql`,
- в логах нет критических ошибок.

## 6. Что делать, если `git pull` блокируется

Если конфликтует локальный файл (например `scripts/release.sh`):

```bash
cp scripts/release.sh backups/release.sh.local.$(date +%F_%H-%M-%S)
git checkout -- scripts/release.sh
git pull origin master
```

Если мешает untracked файл:

```bash
mv scripts/backup-before-deploy.sh.local.bak backups/backup-before-deploy.sh.local.bak.$(date +%F_%H-%M-%S)
```

## 7. Частые ошибки и быстрые решения

### Ошибка: `password authentication failed for user ...`

- Проверить `.env`:
  - `DATABASE_URL`
  - `POSTGRES_USER`
  - `POSTGRES_PASSWORD`
- Должен быть одинаковый пароль в `DATABASE_URL` и `POSTGRES_PASSWORD`.

### Ошибка: сайт без стилей (голый HTML)

Причина: `collectstatic` не попала в running `web` контейнер.

Исправление:

```bash
docker compose up -d db redis web celery celery-beat
docker compose exec web python manage.py collectstatic --noinput
docker compose restart web
```

### Ошибка: `sync_onec timed out`

Это обычно сеть/доступность 1С, не БД.

```bash
docker compose exec web python manage.py sync_onec
```

Повторить через 30-60 секунд. Проверить доступ до `ONEC_API_BASE_URL`.

## 8. Ручной rollback из backup

Список backup-файлов:

```bash
ls -lh /opt/magnat_trade/backups
```

Восстановление:

```bash
docker compose exec -T db sh -lc 'export PGPASSWORD="$POSTGRES_PASSWORD"; dropdb -U "$POSTGRES_USER" --if-exists "$POSTGRES_DB"; createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
cat /opt/magnat_trade/backups/postgres_YYYY-MM-DD_HH-MM-SS.dump | docker compose exec -T db sh -lc 'export PGPASSWORD="$POSTGRES_PASSWORD"; pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges'
```

## 9. Суперпользователь

```bash
docker compose exec web python manage.py createsuperuser
```

## 10. Краткий ежедневный чек-лист

```bash
cd /opt/magnat_trade
bash scripts/release.sh
docker compose exec web python manage.py sync_onec
docker compose exec web python manage.py shell -c "from products.models import Product; print(Product.objects.count())"
docker compose logs --tail=80 web
```
