"""Оформление заказа каталога 1С из HTML-корзины: orders.Order + выгрузка в 1С."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import F

from orders.models import Order, OrderItem
from products.models import Product as CatalogProduct


def _onec_export_enabled() -> bool:
    return bool(getattr(settings, "ONEC_API_BASE_URL", "").strip())


@transaction.atomic
def place_order_from_catalog_cart_items(
    *,
    user,
    cart_items: list,
    full_name: str,
    email: str,
    address: str,
    payment_method: str,
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
    comment = (
        f"Заказ с сайта (HTML) | {full_name} | {email} | {address} | оплата: {payment_method}"
    )
    price_type = "wholesale" if getattr(user, "user_type", "retail") == "wholesale" else "retail"
    warehouse = getattr(settings, "DEFAULT_WAREHOUSE_ID", "MAIN") or "MAIN"

    order = Order.objects.create(
        user=user,
        total_amount=grand_total,
        status="pending",
        payment_status="pending",
        delivery_status="pending",
        currency="KGS",
        price_type=price_type,
        warehouse_id=warehouse,
        comment=comment,
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
        )
        updated = CatalogProduct.objects.filter(pk=cp.pk, stock__gte=qty).update(
            stock=F("stock") - qty
        )
        if updated != 1:
            msg = f"stock:{cp.pk}"
            raise ValueError(msg)

    if _onec_export_enabled():
        from integrations.tasks import export_order_to_onec

        oid = str(order.id)
        transaction.on_commit(lambda: export_order_to_onec.delay(oid))

    return order
