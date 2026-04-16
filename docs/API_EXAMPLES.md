# REST API (v1) — примеры

Базовый URL: `https://<host>/api/v1/`

Интеграционные эндпоинты требуют заголовок `X-API-Key: <INTEGRATION_API_KEY>` или Basic Auth (`INTEGRATION_BASIC_USER` / `INTEGRATION_BASIC_PASSWORD`).

Рекомендуется заголовок `Idempotency-Key: <uuid>` для всех POST, чтобы повтор запроса не создавал дубликатов.

---

## 1. Синхронизация категорий

`POST /api/v1/categories/sync/`

```http
POST /api/v1/categories/sync/
Content-Type: application/json
X-API-Key: <key>
Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000
```

```json
[
  {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "name": "Бумага",
    "parent_id": null,
    "is_active": true
  }
]
```

Ответ:

```json
{
  "created": 1,
  "updated": 0,
  "total": 1
}
```

---

## 2. Синхронизация товаров

`POST /api/v1/products/sync/`

Сначала должны существовать категории (по коду из 1С). Идентификация только по полю `id` (строковый код 1С, например `НФ-00004612`).

```json
[
  {
    "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "sku": "PAPER-A4",
    "name": "Бумага A4",
    "category_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "prices": {
      "retail": 350.0,
      "wholesale": 300.0
    },
    "stock": 120,
    "unit": "pcs",
    "is_active": true
  }
]
```

Ответ:

```json
{
  "created": 1,
  "updated": 0,
  "total": 1
}
```

---

## 3. Синхронизация клиентов (пользователей)

`POST /api/v1/customers/sync/`

Поиск записи только по `external_id` или `id` (код контрагента в 1С). Если `email` нет в данных 1С, сайт подставит технический адрес `onec-<id>@imported.local`.

```json
[
  {
    "id": "b3a1e1e9-5a2f-4c4b-9b9c-123456789abc",
    "email": "ivan@mail.com",
    "name": "Иванов Иван",
    "phone": "+996700123456",
    "price_type": "retail",
    "entity_type": "individual",
    "is_active": true
  }
]
```

---

## 3.1. Полная синхронизация справочников из 1С (GET → БД)

То же, что `python manage.py sync_onec` и периодическая задача Celery Beat: последовательные запросы к 1С (`categories/categoryList`, `products/productList`, `counterparties/counterpartyList`) и запись в БД.

`POST /api/v1/onec/sync-full/`

Тело не обязательно. Query: `?skip_customers=1` — не подтягивать контрагентов.

```http
POST /api/v1/onec/sync-full/
X-API-Key: <key>
```

Нужны `ONEC_API_BASE_URL` и учётные данные к HTTP-сервису 1С в `.env`.

---

## 4. Выгрузка заказа в 1С (асинхронно, Celery)

`POST /api/v1/orders/export/`

```json
{
  "order_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7"
}
```

Ответ `202`:

```json
{
  "task_id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
  "order_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "status": "queued"
}
```

---

## 5. Обновление статуса заказа (из 1С)

`POST /api/v1/orders/status/`

`id` — номер заказа в 1С (`external_id`) или UUID заказа на сайте.

```json
{
  "entity": "order",
  "id": "ORDER-000124",
  "status": "shipped",
  "payment_status": "paid",
  "delivery_status": "in_transit"
}
```

---

## 6. Webhook оплаты

`POST /api/v1/payments/webhook/`

Тело — JSON. Заголовок `X-Signature` = HMAC-SHA256(raw_body, PAYMENT_WEBHOOK_SECRET) в hex.

```json
{
  "order_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "status": "paid"
}
```

---

## 7. Каталог (GET, без ключа)

- `GET /api/v1/catalog/categories/`
- `GET /api/v1/catalog/products/?category_id=<код_категории_1С>`
- `GET /api/v1/catalog/products/<код_товара_1С>/`

---

## 8. Оформление заказа (сессия пользователя)

`POST /api/v1/checkout/orders/` — требуется авторизация (session cookie после login в Django).

```json
{
  "items": [
    { "product_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479", "quantity": 2 }
  ],
  "price_type": "retail",
  "currency": "KGS",
  "comment": "Заказ с сайта"
}
```

Ответ `201`:

```json
{
  "order_id": "…",
  "total_amount": "700.00",
  "payment_url": "https://…",
  "payment_id": "pay_…"
}
```
