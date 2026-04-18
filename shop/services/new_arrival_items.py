"""Товары на странице «Новинки»: явный список из модели NewArrivalItem."""

from __future__ import annotations

from shop.models import NewArrivalItem


def catalog_new_arrival_product_ids_ordered() -> list[str]:
    return list(
        NewArrivalItem.objects.filter(is_active=True, catalog_product_id__isnull=False)
        .order_by("sort_order", "id")
        .values_list("catalog_product_id", flat=True)
    )


def shop_new_arrival_product_ids_ordered() -> list[int]:
    return list(
        NewArrivalItem.objects.filter(is_active=True, shop_product_id__isnull=False)
        .order_by("sort_order", "id")
        .values_list("shop_product_id", flat=True)
    )
