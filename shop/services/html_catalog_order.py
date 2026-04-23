"""Оформление заказа каталога 1С из HTML-корзины: только orders.Order (не shop.Order).

Демо-заказ по shop.Product обрабатывается в shop.views.checkout без этого модуля.
См. docs/DATA_MODEL_DOMAINS.md
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import F

from orders.models import Order, OrderItem
from products.models import Product as CatalogProduct


def _onec_export_enabled() -> bool:
    return bool(getattr(settings, "ONEC_API_BASE_URL", "").strip())


def _special_instructions_summary(cart_items: list) -> str:
    parts: list[str] = []
    for ci in cart_items:
        note = (ci.special_instructions or "").strip()
        if not note:
            continue
        name = ci.catalog_product.name if ci.catalog_product_id else str(ci.product_id)
        parts.append(f"{name}: {note}")
    return " | ".join(parts)


@transaction.atomic
def place_order_from_catalog_cart_items(
    *,
    user,
    cart_items: list,
    full_name: str,
    email: str,
    phone: str,
    address: str,
    payment_method: str,
    delivery_method: str,
    order_comment: str,
    subtotal: Decimal,
    shipping_fee: Decimal,
) -> Order:
    """
    Создаёт orders.Order, позиции, списывает остатки products.Product.
    Выгрузку в 1С ставит в очередь после коммита (Celery).
    """
    if not user.is_authenticated:
        msg = "Требуется вход"
        raise ValueError(msg)
    if _onec_export_enabled() and not getattr(user, "external_id", None):
        msg = "no_external_id"
        raise ValueError(msg)

    grand_total = subtotal + shipping_fee
    special_notes = _special_instructions_summary(cart_items)
    comment = (
        "Заказ с сайта (HTML) | "
        f"{full_name} | {email} | {phone} | {address} | "
        f"доставка: {delivery_method} ({shipping_fee}) | оплата: {payment_method} | "
        f"комментарий: {order_comment or '-'} | "
        f"особые отметки: {special_notes or '-'}"
    )
    price_type = "wholesale" if getattr(user, "user_type", "retail") == "wholesale" else "retail"
    warehouse = getattr(settings, "DEFAULT_WAREHOUSE_ID", "MAIN") or "MAIN"

    order = Order.objects.create(
        user=user,
        total_amount=grand_total,
        shipping_fee=shipping_fee,
        delivery_method=delivery_method,
        delivery_full_name=full_name,
        delivery_email=email,
        delivery_phone=phone,
        delivery_address=address,
        status="pending",
        payment_status="pending",
        delivery_status="pending",
        currency="KGS",
        price_type=price_type,
        warehouse_id=warehouse,
        comment=comment,
        customer_comment=order_comment or "",
    )

    for ci in cart_items:
        cp = ci.catalog_product
        qty = ci.quantity
        price = ci.price
        OrderItem.objects.create(
            order=order,
            product_id=str(cp.pk),
            quantity=qty,
            price=price,
            name_snapshot=cp.name,
            special_instructions=(ci.special_instructions or "").strip(),
        )
        updated = CatalogProduct.objects.filter(pk=cp.pk, stock__gte=qty).update(
            stock=F("stock") - qty
        )
        if updated != 1:
            msg = f"stock:{cp.pk}"
            raise ValueError(msg)

    if _onec_export_enabled():
        from integrations.tasks import queue_export_order_to_onec

        oid = str(order.id)
        transaction.on_commit(lambda: queue_export_order_to_onec(oid))

    return order
