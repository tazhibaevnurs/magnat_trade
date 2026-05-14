"""Соответствие цен после синхронизации из GET productList (флаг одной стороны 1С)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from products.models import Product
from products.repositories.product_repository import ProductRepository


@pytest.mark.django_db
def test_onec_swap_corrects_permuted_json_keys(category) -> None:
    """
    Когда ключи retail/wholesale на стороне 1С отражают суммы перекрёстно,
    включается ``onec_product_list_swaps_price_keys`` (pull из 1С).
    Ожидание после свапа: розница Django = бизнес-розница из примера.
    """
    pid = "НФ-SWAP-PRICE-TEST-001"
    ProductRepository.upsert_from_payload(
        {
            "id": pid,
            "sku": "",
            "name": "Проверка свапа",
            "category_id": str(category.id),
            "prices": {"retail": 230.0, "wholesale": 299.0},
            "stock": 1,
            "unit": "шт",
            "is_active": True,
        },
        onec_product_list_swaps_price_keys=True,
    )
    p = Product.objects.get(id=pid)
    assert p.retail_price == Decimal("299")
    assert p.wholesale_price == Decimal("230")


@pytest.mark.django_db
def test_integration_post_semantics_without_swap(category) -> None:
    """POST /api/v1/products/sync/ не использует свап: retail в JSON → retail_price в модели."""
    pid = "НФ-NOSWAP-PRICE-TEST-002"
    ProductRepository.upsert_from_payload(
        {
            "id": pid,
            "sku": "",
            "name": "Канонический payload",
            "category_id": str(category.id),
            "prices": {"retail": 299.0, "wholesale": 230.0},
            "stock": 1,
            "unit": "шт",
            "is_active": True,
        },
    )
    p = Product.objects.get(id=pid)
    assert p.retail_price == Decimal("299")
    assert p.wholesale_price == Decimal("230")
