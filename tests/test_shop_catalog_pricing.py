"""Отображаемая цена витрины строго из полей retail_price / wholesale_price."""

from __future__ import annotations

from decimal import Decimal

import pytest

from products.models import Product
from shop.pricing import catalog_unit_price, user_sees_wholesale_prices


class _Guest:
    is_authenticated = False


class _WholesaleUser:
    is_authenticated = True
    user_type = "wholesale"


class _RetailUser:
    is_authenticated = True
    user_type = "retail"


@pytest.mark.django_db
def test_catalog_unit_price_uses_model_fields_directly(category) -> None:
    p = Product.objects.create(
        id="НФ-T-PRICE-MAP",
        sku="",
        name="Цена как в БД",
        category=category,
        retail_price=Decimal("299.00"),
        wholesale_price=Decimal("230.00"),
        stock=1,
        unit="шт",
        is_active=True,
    )
    assert catalog_unit_price(p, _Guest()) == Decimal("299.00")
    assert catalog_unit_price(p, _RetailUser()) == Decimal("299.00")
    assert catalog_unit_price(p, _WholesaleUser()) == Decimal("230.00")


def test_user_sees_wholesale_prices_only_for_wholesale_type() -> None:
    assert user_sees_wholesale_prices(None) is False
    assert user_sees_wholesale_prices(_Guest()) is False
    assert user_sees_wholesale_prices(_RetailUser()) is False
    assert user_sees_wholesale_prices(_WholesaleUser()) is True
