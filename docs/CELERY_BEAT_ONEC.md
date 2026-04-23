# Celery Beat: периодическая синхронизация с 1С

Пути HTTP-сервиса задаются относительно `ONEC_API_BASE_URL` (база до `/hs`, без слэша в конце), например:

`https://rdp.it-help.kg:4443/bereke_test/hs`

| URL (подставляется к базе) | Назначение |
|----------------------------|------------|
| `categories_products/categoryProductList` | Дерево категорий и соответствие товар ↔ категория |
| `products/productList` | Номенклатура, цены, остатки |
| `counterparties/counterpartyList` | Контрагенты (если не отключено) |
| `categories/categoryList` | Дополнительный справочник категорий только при включённом `ONEC_LEGACY_CATEGORY_LIST_FALLBACK` и недостающих кодах после синхронизации |

## Что уже есть в коде

- **`integrations.tasks.sync_all_from_onec`** — полный цикл: `categoryProductList` → синхронизация категорий → зеркало `shop` → `productList` → при необходимости контрагенты (`counterpartyList`, если `ONEC_BEAT_SKIP_CUSTOMERS=false`).
- **`integrations.tasks.sync_products_from_onec`** — ускоренное обновление номенклатуры (`productList`, при пустом кэше ещё `categoryProductList`).

Расписание задаётся в **`magnat_trade_project/settings.py`** через **`CELERY_BEAT_SCHEDULE`** (переменные окружения ниже).

## Интервал 60 минут для «всего сразу»

1. В `.env`:
   - `ONEC_API_BASE_URL=https://rdp.it-help.kg:4443/bereke_test/hs` (и учётные данные Basic/Bearer).
   - `ONEC_BEAT_SYNC_ENABLED=true`
   - **`ONEC_BEAT_PRODUCT_SYNC_MINUTES=0`** — отключить частую задачу «только товары».
   - **`ONEC_BEAT_FULL_SYNC_MINUTES=60`** — полная синхронизация раз в час.

2. Запуск процессов (нужны **Redis** и оба процесса):

```bash
celery -A magnat_trade_project worker -l info
celery -A magnat_trade_project beat -l info
```

Docker Compose уже содержит сервисы `celery` и `celery-beat`:

```bash
docker compose up -d redis db web celery celery-beat
```

Пересоздавать Beat при каждом деплое не нужно: достаточно держать контейнер/сервис `celery-beat` запущенным; расписание подхватывается из настроек при старте процесса.

## Два расписания (чаще цены, реже полный каталог)

По умолчанию в `.env.example`: товары каждые 5 минут + полная синхронизация каждые 60 минут. Так можно оставить, если нужны частые обновления остатков/цен между полными прогонами.

## Отключить синхронизацию по расписанию

`ONEC_BEAT_SYNC_ENABLED=false` или `ONEC_BEAT_FULL_SYNC_MINUTES=0` (и при необходимости `ONEC_BEAT_PRODUCT_SYNC_MINUTES=0`).

## Ручной запуск без Beat

```bash
python manage.py sync_onec --help
```

Или API (с ключом интеграции): `POST /api/v1/onec/sync-full/` (см. `api/urls.py`).
