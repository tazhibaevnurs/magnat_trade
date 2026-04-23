# Деплой Magnat Trade (Docker / VPS)

## 1. Переменные окружения (обязательно для продакшена)

Скопируйте `.env.example` → `.env` на сервере и задайте минимум:

| Переменная | Описание |
|------------|----------|
| `DJANGO_DEBUG=false` | Продакшен |
| `DJANGO_SECRET_KEY` | Уникальный длинный ключ (не значение по умолчанию) |
| `DJANGO_ALLOWED_HOSTS` | Домены через запятую: `mysite.ru,www.mysite.ru` |
| `DJANGO_TIME_ZONE` | Например `Asia/Bishkek` |

База данных — рекомендуемо PostgreSQL:

- **`DATABASE_URL`** — PostgreSQL (Neon, Supabase, собственный сервер).
- Для Docker Compose по умолчанию используется сервис `db` (PostgreSQL 16).

Redis обязателен для Celery:

- `REDIS_URL=redis://redis:6379/0` (имя сервиса из compose)
- На VPS без Docker: `redis://127.0.0.1:6379/0`

HTTPS за reverse proxy:

- `SESSION_COOKIE_SECURE=true`, `CSRF_COOKIE_SECURE=true`, `SECURE_SSL_REDIRECT=true` (если TLS на nginx/балансировщике).

Интеграция 1С:

- `ONEC_API_BASE_URL`, учётные данные Basic/Bearer — см. `.env.example`.

Полный список см. `.env.example` и [CELERY_BEAT_ONEC.md](CELERY_BEAT_ONEC.md).

## 2. Docker Compose (рекомендуемый стек)

На сервере с установленным Docker:

```bash
docker compose build
docker compose up -d
```

Поднимется: **PostgreSQL**, **Redis**, **web** (Gunicorn), **celery**, **celery-beat**.

- Миграции и `collectstatic` выполняются отдельным release-шагом (безопаснее, чем автозапуск в `web`).
- Загрузки пользователей (**media**) монтируются в том **`media_data`** — данные переживают пересборку образа.

Проверка:

```bash
docker compose ps
docker compose logs -f web
```

Безопасное обновление после выкладки кода:

```bash
bash scripts/release.sh
```

## 3. За reverse proxy (nginx / Caddy)

Проксируйте `proxy_pass` на `127.0.0.1:8000` (или порт из `ports` в compose). Отдайте **`/media/`** с диска (тот же путь, что **`MEDIA_ROOT`** в контейнере), либо смонтируйте том `media_data` в nginx.

Заголовки для Django за HTTPS:

```nginx
proxy_set_header Host $host;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
```

## 4. Без Docker (VPS)

1. Python 3.12+, виртуальное окружение, `pip install -r requirements.txt` (+ при MySQL `requirements-mysql.txt`).
2. PostgreSQL или MySQL, Redis.
3. `python manage.py migrate`, `python manage.py collectstatic --noinput`.
4. Gunicorn (systemd): например `gunicorn magnat_trade_project.wsgi:application --bind 127.0.0.1:8000 --workers 3 --timeout 120`.
5. Отдельные systemd-юниты для `celery worker` и `celery beat` с тем же `.env`.

На **Windows** для локальной отладки Celery: worker с `--pool=solo`, должен быть запущен Redis.

## 5. Чеклист перед продом

- [ ] `DJANGO_DEBUG=false`, `SECRET_KEY`, `ALLOWED_HOSTS`
- [ ] База и миграции применены
- [ ] `collectstatic` выполнен (в Docker — автоматически в `web`)
- [ ] Redis доступен приложению и Celery
- [ ] Запущены **worker** и **beat** (или контейнеры `celery`, `celery-beat`)
- [ ] HTTPS и cookie-флаги при работе по HTTPS

## 6. Vercel / serverless

См. [DEPLOY_VERCEL_DATABASE.md](DEPLOY_VERCEL_DATABASE.md) — ограничения serverless; долгоживущие Celery worker/beat там обычно не подходят, нужен отдельный worker-хост или внешний планировщик.
