from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from products.models import Product


def _to_decimal(val: Any, default: Decimal = Decimal("0")) -> Decimal:
    """Безопасное преобразование цены из JSON (число, строка с запятой, None)."""
    if val is None or val == "":
        return default
    if isinstance(val, Decimal):
        return val
    try:
        s = str(val).strip().replace(" ", "").replace("\xa0", "")
        if "," in s and "." in s:
            s = s.replace(",", "")
        elif "," in s and "." not in s:
            s = s.replace(",", ".")
        return Decimal(s)
    except (InvalidOperation, ValueError, TypeError):
        return default


def _extract_retail_wholesale(data: dict[str, Any]) -> tuple[Decimal, Decimal]:
    """
    Извлекает розницу и опт из payload 1С / интеграции.

    Поддерживаются:
    - prices: { "retail": n, "wholesale": n } и варианты регистра / синонимы;
    - prices: [ { "type": "retail", "value": n }, ... ];
    - плоские retail_price / wholesale_price на корне.
    """
    raw_prices = data.get("prices")
    retail: Decimal | None = None
    wholesale: Decimal | None = None

    if isinstance(raw_prices, dict):
        for key in (
            "retail",
            "Retail",
            "priceRetail",
            "PriceRetail",
            "розница",
            "Розница",
        ):
            if key in raw_prices and raw_prices[key] is not None:
                retail = _to_decimal(raw_prices[key])
                break
        for key in (
            "wholesale",
            "Wholesale",
            "priceWholesale",
            "PriceWholesale",
            "опт",
            "Опт",
        ):
            if key in raw_prices and raw_prices[key] is not None:
                wholesale = _to_decimal(raw_prices[key])
                break
    elif isinstance(raw_prices, list):
        for item in raw_prices:
            if not isinstance(item, dict):
                continue
            t = str(item.get("type") or item.get("kind") or item.get("name") or "").strip().lower()
            v = item.get("value")
            if v is None:
                v = item.get("price")
            if v is None:
                continue
            if retail is None and (
                "розниц" in t
                or "retail" in t
                or t in ("р", "розница")
            ):
                retail = _to_decimal(v)
            if wholesale is None and ("опт" in t or "wholesale" in t or "wholesal" in t):
                wholesale = _to_decimal(v)

    if retail is None:
        v = data.get("retail_price")
        if v is not None:
            retail = _to_decimal(v)
    if wholesale is None:
        v = data.get("wholesale_price")
        if v is not None:
            wholesale = _to_decimal(v)

    if retail is None:
        retail = Decimal("0")
    if wholesale is None:
        wholesale = Decimal("0")

    return retail, wholesale


class ProductRepository:
    @staticmethod
    def upsert_from_payload(
        data: dict[str, Any],
        *,
        onec_product_list_swaps_price_keys: bool = False,
    ) -> tuple[Product, bool]:
        """
        Синхронизация по коду номенклатуры из 1С.
        sku и name не используются для поиска записи.

        ``onec_product_list_swaps_price_keys``: для GET productList, если в JSON ключ
        ``retail`` фактически соответствует оптовой цене, а ``wholesale`` — рознице
        (см. ONEC_PRODUCT_LIST_SWAP_PRICE_KEYS). Для POST интеграций оставлять False.
        """
        pk = str(data["id"]).strip()
        category_id = str(data["category_id"]).strip()
        retail, wholesale = _extract_retail_wholesale(data)
        if onec_product_list_swaps_price_keys:
            retail, wholesale = wholesale, retail

        defaults = {
            "sku": (data.get("sku") or "").strip(),
            "name": data["name"],
            "category_id": category_id,
            "retail_price": retail,
            "wholesale_price": wholesale,
            "stock": int(data.get("stock", 0) or 0),
            "unit": (data.get("unit") or "pcs")[:32],
            "is_active": bool(data.get("is_active", True)),
        }

        obj, created = Product.objects.update_or_create(
            id=pk,
            defaults=defaults,
        )
        return obj, created
