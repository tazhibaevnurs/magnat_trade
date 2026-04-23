"""Оформление демо-заказа (shop.Product) в единую таблицу orders_order."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import F

from orders.constants import DEMO_PRODUCT_LINE_PREFIX
from orders.models import Order, OrderItem
from shop.models import InventoryTransaction, Product as ShopProduct


def _special_instructions_summary(cart_items: list) -> str:
    parts: list[str] = []
    for ci in cart_items:
        note = (ci.special_instructions or "").strip()
        if not note:
            continue
        name = ci.product.name if ci.product_id else str(ci.product_id)
        parts.append(f"{name}: {note}")
    return " | ".join(parts)


@transaction.atomic
def place_demo_order_from_cart_items(
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
    Создаёт orders.Order и строки с product_id DEMO:{shop_product_pk}.
    Списывает остатки shop.Product; пишет InventoryTransaction с catalog_order.
    Без выгрузки в 1С.
    """
    grand_total = subtotal + shipping_fee
    special_notes = _special_instructions_summary(cart_items)
    comment = (
        "Демо-витрина | "
        f"{full_name} | {email} | {phone} | {address} | "
        f"доставка: {delivery_method} ({shipping_fee}) | оплата: {payment_method} | "
        f"комментарий: {order_comment or '-'} | "
        f"особые отметки: {special_notes or '-'}"
    )
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
        price_type="retail",
        warehouse_id=warehouse,
        comment=comment,
        customer_comment=order_comment or "",
    )

    for ci in cart_items:
        sp = ci.product
        assert sp is not None
        stock_before = sp.stock
        if stock_before < ci.quantity:
            raise ValueError(f"stock:{sp.pk}")
        rows = ShopProduct.objects.filter(pk=sp.pk, stock__gte=ci.quantity).update(
            stock=F("stock") - ci.quantity
        )
        if rows != 1:
            raise ValueError(f"stock:{sp.pk}")
        stock_after = stock_before - ci.quantity

        unit_price = ci.price
        OrderItem.objects.create(
            order=order,
            product_id=f"{DEMO_PRODUCT_LINE_PREFIX}{sp.pk}",
            quantity=ci.quantity,
            price=unit_price,
            name_snapshot=sp.name,
            special_instructions=(ci.special_instructions or "").strip(),
        )

        InventoryTransaction.objects.create(
            product=sp,
            catalog_order=order,
            order=None,
            transaction_type="sale",
            quantity_change=-ci.quantity,
            stock_before=stock_before,
            stock_after=stock_after,
            notes=f"Демо-заказ {order.id} — {full_name}",
            created_by=(
                user if user is not None and getattr(user, "is_authenticated", False) else None
            ),
        )

    return order
