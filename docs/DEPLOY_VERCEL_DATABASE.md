# База данных на Supabase + Vercel (товары и категории)

Проект использует **PostgreSQL** через **`DATABASE_URL`** (`magnat_trade_project/settings.py`, `dj-database-url`, `psycopg`).

Ниже — подключение **[Supabase](https://supabase.com)** как основной БД для продакшена и заполнение каталога.

---

## 1. Проект в Supabase

1. Зайдите на [https://supabase.com](https://supabase.com) → **Start your project** / войдите в аккаунт.
2. **New project**:
   - **Name** — например `magnat-trade`
   - **Database password** — сохраните в менеджере паролей (нужен для строки подключения).
   - **Region** — ближе к пользователям (например **Frankfurt** / **London**).
3. Дождитесь статуса **Healthy** (1–2 минуты).

---

## 2. Строка подключения `DATABASE_URL`

1. В проекте Supabase: **Project Settings** (шестерёнка) → **Database**.
2. Прокрутите до **Connection string** → вкладка **URI**.
3. Режим:
   - **Transaction pooler** (рекомендуется для **Vercel** / serverless) — хост вида **`...@aws-0-....pooler.supabase.com:6543`** — много коротких запросов, меньше проблем с лимитом соединений.
   - **Session pooler** или **Direct** — порт **5432**; для Django на serverless чаще берут **Transaction** с портом **6543**.

4. Подставьте **свой пароль** вместо `[YOUR-PASSWORD]` в строке и скопируйте **полный URI**.

Пример формата (ваш хост и пользователь будут своими):

```text
postgresql://postgres.xxxxx:[YOUR-PASSWORD]@aws-0-eu-central-1.pooler.supabase.com:6543/postgres
```

Часто в конце добавляют `?sslmode=require` — если в панели его нет, допишите вручную:

```text
...6543/postgres?sslmode=require
```

**Важно:** не публикуйте URI в Git и не вставляйте в открытые чаты.

В коде для **pooler** уже выставляется **`conn_max_age=0`** (см. `settings.py`); при прямом подключении к `:5432` можно задать `DATABASE_CONN_MAX_AGE=600` в Vercel при необходимости.

---

## 3. Переменные в Vercel

1. [vercel.com](https://vercel.com) → ваш проект → **Settings** → **Environment Variables**.
2. Добавьте:

| Переменная | Значение |
|------------|----------|
| `DATABASE_URL` | Полный URI из шага 2 (Supabase URI). |
| `DJANGO_SECRET_KEY` | Случайная длинная строка. |
| `DJANGO_DEBUG` | `false` |
| `DJANGO_ALLOWED_HOSTS` | Ваш домен, напр. `magnat-trade.vercel.app` и свой домен через запятую. |

3. Сохраните для **Production** (и при необходимости **Preview**).
4. **Deployments** → последний деплой → **⋯** → **Redeploy** (чтобы подтянулись секреты и снова выполнились `collectstatic` + `migrate` из `vercel.json`).

После деплоя таблицы Django создаются в Supabase (**migrate**), данные каталога нужно загрузить (раздел 5).

---

## 4. Проверка в Supabase

**Table Editor** или **SQL Editor**:

```sql
SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;
```

Должны появиться таблицы Django (`django_migrations`, `auth_*`, `products_*`, …) после успешного деплоя.

---

## 5. Заполнить категории и товары

### Вариант A — из 1С (основной сценарий)

1. Локально в **`.env`** укажите **тот же** `DATABASE_URL`, что в Vercel, и параметры **1С** (`ONEC_API_BASE_URL`, авторизация и т.д., см. `.env.example`).
2. Выполните:

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py sync_onec
python manage.py mirror_shop_categories
```

3. Откройте сайт на Vercel — данные читаются из Supabase.

### Вариант B — дамп с локальной SQLite

```bash
python manage.py dumpdata products shop --indent 2 -o backup.json
# в .env только DATABASE_URL на Supabase
python manage.py migrate
python manage.py loaddata backup.json
python manage.py mirror_shop_categories
```

---

## 6. Картинки (media)

Файлы в `/media/` на Vercel без внешнего хранилища не сохраняются между деплоями. Для превью товаров позже подключите **S3 / Supabase Storage** или URL из 1С — отдельная настройка `STORAGES`.

---

## 7. Чеклист

- [ ] Проект Supabase создан, `DATABASE_URL` (pooler :6543 или direct :5432) скопирован.
- [ ] В Vercel заданы `DATABASE_URL`, `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=false`.
- [ ] Выполнен Redeploy.
- [ ] Локально с тем же `DATABASE_URL`: `migrate` → `sync_onec` → `mirror_shop_categories` (или loaddata).

---

## Дополнительно: Neon / другой Postgres

Любой PostgreSQL с рабочим URI подходит — шаги 3–5 те же, только строку берёте не из Supabase, а из панели провайдера.
