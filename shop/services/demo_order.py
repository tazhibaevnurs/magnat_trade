"""Оформление демо-заказа (shop.Product) в единую таблицу orders_order."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import F

from orders.constants import DEMO_PRODUCT_LINE_PREFIX
from orders.models import Order, OrderItem
from shop.models import InventoryTransaction, Product as ShopProduct


@transaction.atomic
def place_demo_order_from_cart_items(
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
    Создаёт orders.Order и строки с product_id DEMO:{shop_product_pk}.
    Списывает остатки shop.Product; пишет InventoryTransaction с catalog_order.
    Без выгрузки в 1С.
    """
    grand_total = subtotal + shipping_fee
    comment = (
        f"Демо-витрина | {full_name} | {email} | {address} | оплата: {payment_method}"
    )
    warehouse = getattr(settings, "DEFAULT_WAREHOUSE_ID", "MAIN") or "MAIN"

    order = Order.objects.create(
        user=user,
        total_amount=grand_total,
        shipping_fee=shipping_fee,
        delivery_full_name=full_name,
        delivery_email=email,
        delivery_address=address,
        status="pending",
        payment_status="pending",
        delivery_status="pending",
        currency="KGS",
        price_type="retail",
        warehouse_id=warehouse,
        comment=comment,
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
