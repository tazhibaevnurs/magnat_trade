"""Товары на странице «Акции»: явный список из модели PromotionItem."""

from __future__ import annotations

from shop.models import PromotionItem


def catalog_promotion_product_ids_ordered() -> list[str]:
    return list(
        PromotionItem.objects.filter(is_active=True, catalog_product_id__isnull=False)
        .order_by("sort_order", "id")
        .values_list("catalog_product_id", flat=True)
    )


def shop_promotion_product_ids_ordered() -> list[int]:
    return list(
        PromotionItem.objects.filter(is_active=True, shop_product_id__isnull=False)
        .order_by("sort_order", "id")
        .values_list("shop_product_id", flat=True)
    )
