"""
Дублирует категории из приложения products (1С) в shop.Category,
чтобы шапка, сайдбар и фильтры каталога (slug) работали без смены модели Product.
"""

from __future__ import annotations

from collections import deque

from django.core.cache import cache
from django.db import transaction

from integrations.parsers.category_product_tree import CATEGORY_TREE_ROOT_ORDER_CACHE_KEY


def mirror_products_categories_to_shop() -> dict[str, int]:
    """
    Создаёт/обновляет shop.Category по данным products.Category (порядок: от корней к листьям).
    Возвращает счётчики для логов.
    """
    from products.models import Category as PC
    from shop.models import Category as SC

    roots_qs = PC.objects.filter(parent__isnull=True)
    order = cache.get(CATEGORY_TREE_ROOT_ORDER_CACHE_KEY)
    if isinstance(order, list) and order:
        roots: list[PC] = []
        seen: set[str] = set()
        for pid in order:
            try:
                pc = PC.objects.get(pk=str(pid))
            except PC.DoesNotExist:
                continue
            roots.append(pc)
            seen.add(str(pc.pk))
        for pc in roots_qs.exclude(pk__in=seen).order_by("name"):
            roots.append(pc)
    else:
        roots = list(roots_qs.order_by("name"))
    ordered: list[PC] = []
    q: deque[PC] = deque(roots)
    seen: set[str] = set()
    while q:
        pc = q.popleft()
        if pc.pk in seen:
            continue
        seen.add(pc.pk)
        ordered.append(pc)
        for child in PC.objects.filter(parent_id=pc.pk).order_by("name"):
            q.append(child)

    remaining = set(PC.objects.values_list("id", flat=True)) - seen
    for pk in sorted(remaining):
        ordered.append(PC.objects.get(pk=pk))

    created = 0
    updated = 0
    with transaction.atomic():
        for pc in ordered:
            parent_sc = None
            if pc.parent_id:
                try:
                    parent_pc = PC.objects.get(pk=pc.parent_id)
                    parent_sc = SC.objects.filter(slug=parent_pc.slug).first()
                except PC.DoesNotExist:
                    parent_sc = None
            obj, was_created = SC.objects.update_or_create(
                slug=pc.slug,
                defaults={
                    "name": (pc.name or "")[:200],
                    "parent": parent_sc,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

    return {"shop_categories_created": created, "shop_categories_updated": updated, "total": len(ordered)}
