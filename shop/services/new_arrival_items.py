"""Товары на странице «Новинки»: явный список из модели NewArrivalItem."""

from __future__ import annotations

from datetime import datetime, time as dtime
from typing import Any

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from shop.models import NewArrivalItem


def shop_new_arrivals_include_since_datetime():
    """Нижняя граница даты для авто-пополнения «Новинок» каталогом 1С; None если отключено."""
    d = getattr(settings, "SHOP_NEW_ARRIVALS_AUTO_SINCE", None)
    if not d:
        return None
    return timezone.make_aware(datetime.combine(d, dtime.min))


def build_new_arrivals_or_q(*, manual_pks: list[Any]) -> Q | None:
    """Объединяет фильтры: активные записи NewArrivalItem и товары с created_at >= SHOP_NEW_ARRIVALS_AUTO_SINCE.

    Вернёт ``None``, если и ручной список пуст и авто-дата выключена (страницу нужно считать пустой по правилам витрины).
    """
    clauses: list[Q] = []
    if manual_pks:
        clauses.append(Q(pk__in=manual_pks))
    since_dt = shop_new_arrivals_include_since_datetime()
    if since_dt is not None:
        clauses.append(Q(created_at__gte=since_dt))
    if not clauses:
        return None
    combined = clauses[0]
    for c in clauses[1:]:
        combined |= c
    return combined


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
