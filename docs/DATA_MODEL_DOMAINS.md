# Две предметные области данных в Magnat Trade

В одной базе данных Django сосуществуют **две логические схемы**. Их нельзя смешивать при запросах и отчётах без явного понимания источника.

---

## Область A — каталог и заказы из 1С (`products_*`, `orders_*`)

**Назначение:** номенклатура и цены из 1С, заказы через REST API оплаты и через HTML-корзину при выборе **товаров каталога** (`products.Product`).

| Таблица | Роль |
|---------|------|
| `products_category` | дерево категорий (id из 1С) |
| `products_product` | товар: `retail_price`, `wholesale_price`, остаток |
| `products_productimage` | галерея |
| `orders_order` | заказ (**UUID**), сумма, `price_type`, оплата, склад, ошибки выгрузки в 1С |
| `orders_orderitem` | строка: `product_id` строкой (= id номенклатуры), цена, количество |

**Где создаются заказы области A:**

- `POST /api/checkout/order/` (`api/checkout.py`) — только авторизованный пользователь; опт проверяется по `user_type`.
- Оформление на сайте: корзина с позициями **`catalog_product`** → `shop/services/html_catalog_order.place_order_from_catalog_cart_items()` → **`orders_order` / `orders_orderitem`**, списание **`products_product.stock`**.
- Демо-корзина только с **`shop.Product`**: `shop/services/demo_order.place_demo_order_from_cart_items()` → те же **`orders_order` / `orders_orderitem`**, строки с `product_id` вида `DEMO:{shop_product_pk}` (выгрузка в 1С такие строки отбраковывает); списание **`shop_product.stock`**, движения — `shop_inventorytransaction` с полем **`catalog_order`** → `orders_order`.

Публичный каталог REST: `GET /api/catalog/products/` — см. ограничение видимости оптовой цены в коде (`ProductOutSerializer`).

---

## Область B — витрина и демо-данные (`shop_*`)

**Назначение:** шаблоны UI, корзина (общая для обеих номенклатур), профиль, обратная связь, **устаревший демо-каталог** (`shop.Product`), отдельная модель заказа для оформления **только демо-товаров**.

| Таблица | Роль |
|---------|------|
| `shop_category` | категории **демо**-витрины (не 1С) |
| `shop_product` | демо-товар (slug, свои цены/остатки) |
| `shop_productimage` | изображения демо-товаров |
| `shop_cart` / `shop_cartitem` | корзина: строка либо на `shop_product`, либо на `products_product` |
| `shop_userprofile` | профиль (адрес, телефон, валюта, фото) |
| `shop_address` | адреса доставки |
| `shop_order` | **legacy:** старые демо-заказы до унификации (целочисленный PK); новые демо-заказы не создаются |
| `shop_orderitem` | **legacy:** строки старых демо-заказов → FK на **`shop_product`** |
| `shop_feedback` | обратная связь |
| `shop_inventorytransaction` | движения склада по **`shop_product`** |

**Legacy `shop_order`:** остаётся в БД для истории; админка и отчёты по старым строкам могут ссылаться на **`admin:shop_order_*`**.

Правило в коде: нельзя смешивать в одном заказе каталог 1С и демо-товары (`has_catalog and has_shop`). Новый демо-checkout создаёт **`orders_order`**, не `shop_order`.

---

## Сводка: какая таблица заказов когда используется

| Сценарий | Таблицы заказов |
|----------|-----------------|
| Клиент оформляет корзину с товарами **`products.Product`** | `orders_order`, `orders_orderitem` |
| Клиент оформляет корзину только с **`shop.Product`** | `orders_order`, `orders_orderitem` (строки `DEMO:…`) |
| Мобильный/внешний клиент через API оплаты | `orders_order`, `orders_orderitem` |
| Старые демо-заказы (до миграции потока) | `shop_order`, `shop_orderitem` |

Личный кабинет `/orders/` читает **`orders_order`**; учёт очень старых `shop_order` при необходимости — отдельным запросом или миграцией данных.

---

## Интеграции и пользователи

| Таблица | Область |
|---------|---------|
| `integrations_onecinteractionlog` | технический журнал вызовов 1С (не «товары») |
| `users_user`, `users_wholesaleupgraderequest` | общие для сайта; `external_id` относится к контрагенту 1С |

---

## Рекомендации для разработки

1. **Именование в коде:** импорты вида `from orders.models import Order` и `from shop.models import Order` — разные модели; в новом коде предпочитать алиасы: `CatalogOrder` / `ShopDemoOrder` при одновременном импорте.
2. **Отчёты и аналитика:** явно UNION или два отчёта — не суммировать заказы без фильтра по источнику.
3. **Долгосрочно:** при отказе от демо-витрины можно упростить схему и оставить только `orders_*` + `products_*`; до этого момента документируйте оба потока в MR/релизах.

---

*Файл можно расширять ссылками на конкретные view и URL по мере рефакторинга.*
