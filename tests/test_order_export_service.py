"""Формирование payload для 1С."""

from __future__ import annotations

import pytest


@pytest.mark.django_db
def test_build_payload_matches_onec_contract(order_with_items):
    from orders.services.order_export import OrderExportService

    payload = OrderExportService.build_payload(order_with_items)
    assert payload["external_order_id"] == str(order_with_items.id)
    assert payload["customer_id"] == str(order_with_items.user.external_id)
    assert payload["currency"] == "KGS"
    assert payload["source"] == "website"
    assert len(payload["items"]) == 1
    assert payload["items"][0]["product_id"] == str(order_with_items.items.first().product_id)
    assert payload["items"][0]["quantity"] == order_with_items.items.first().quantity
    assert "total_amount" in payload


@pytest.mark.django_db
def test_build_payload_requires_user_external_id(user_with_external, product, product_id):
    from decimal import Decimal

    from orders.models import Order, OrderItem
    from orders.services.order_export import OrderExportService

    user_with_external.external_id = None
    user_with_external.save(update_fields=["external_id"])

    order = Order.objects.create(
        user=user_with_external,
        total_amount=Decimal("100.00"),
        status="pending",
        payment_status="pending",
        delivery_status="pending",
    )
    OrderItem.objects.create(
        order=order,
        product_id=product_id,
        quantity=1,
        price=Decimal("100.00"),
        name_snapshot="x",
    )

    with pytest.raises(ValueError, match="external_id"):
        OrderExportService.build_payload(order)
