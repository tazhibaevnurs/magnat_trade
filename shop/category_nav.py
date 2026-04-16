"""Дерево категорий для меню и API поиска в выпадающем каталоге."""

from __future__ import annotations

from typing import Any

from django.core.cache import cache

from integrations.parsers.category_product_tree import CATEGORY_TREE_ROOT_ORDER_CACHE_KEY

from .models import Category


def get_shop_catalog_nav_roots_and_allowed_slugs() -> tuple[list[Category], set[str] | None]:
    """
    Корни для шапки/сайдбара: при наличии дерева из 1С (id N-*) — только оно, порядок как в categoryProductList.
    """
    from products.models import Category as ProductCategory

    if not ProductCategory.objects.filter(id__startswith="N-").exists():
        roots = list(
            Category.objects.filter(parent__isnull=True)
            .prefetch_related("children")
            .order_by("name")
        )
        return roots, None

    order = cache.get(CATEGORY_TREE_ROOT_ORDER_CACHE_KEY)
    pc_roots: list[ProductCategory] = []
    if isinstance(order, list) and order:
        for pid in order:
            try:
                pc_roots.append(ProductCategory.objects.get(pk=str(pid)))
            except ProductCategory.DoesNotExist:
                continue
    else:
        pc_roots = list(
            ProductCategory.objects.filter(parent__isnull=True, id__startswith="N-")
            .order_by("name")
            .prefetch_related("children")
        )

    roots: list[Category] = []
    for pc in pc_roots:
        sc = (
            Category.objects.filter(slug=pc.slug, parent__isnull=True)
            .prefetch_related("children")
            .first()
        )
        if sc:
            roots.append(sc)

    allowed = set(
        ProductCategory.objects.filter(id__startswith="N-").values_list("slug", flat=True)
    )
    return roots, allowed


def get_shop_catalog_product_category_roots():
    """
    Те же корневые категории каталога 1С (products.Category), что и в шапке/каталоге.
    Порядок — как в categoryProductList (кэш CATEGORY_TREE_ROOT_ORDER_CACHE_KEY).
    без «лишних» корней НФ-* из старой синхронизации.
    """
    from products.models import Category as ProductCategory

    if not ProductCategory.objects.filter(id__startswith="N-").exists():
        return list(ProductCategory.objects.filter(parent__isnull=True).order_by("name"))

    order = cache.get(CATEGORY_TREE_ROOT_ORDER_CACHE_KEY)
    pc_roots: list[ProductCategory] = []
    if isinstance(order, list) and order:
        for pid in order:
            try:
                pc_roots.append(ProductCategory.objects.get(pk=str(pid)))
            except ProductCategory.DoesNotExist:
                continue
    else:
        pc_roots = list(
            ProductCategory.objects.filter(parent__isnull=True, id__startswith="N-")
            .order_by("name")
        )
    return pc_roots


def build_category_nav_payload(
    roots: list[Category] | None = None,
    *,
    allowed_descendant_slugs: set[str] | None = None,
) -> list[dict[str, Any]]:
    if roots is None:
        roots = list(
            Category.objects.filter(parent__isnull=True)
            .prefetch_related("children")
            .order_by("name")
        )
    out: list[dict[str, Any]] = []
    for root in roots:
        subs = list(root.children.all())
        if allowed_descendant_slugs is not None:
            subs = [s for s in subs if s.slug in allowed_descendant_slugs]
        out.append(
            {
                "slug": root.slug,
                "name": root.name,
                "subs": [{"slug": s.slug, "name": s.name} for s in subs],
            }
        )
    return out


def filter_category_nav(payload: list[dict[str, Any]], q: str) -> list[dict[str, Any]]:
    q = (q or "").strip().lower()
    if not q:
        return payload
    result: list[dict[str, Any]] = []
    for item in payload:
        subs = item.get("subs") or []
        root_match = q in (item.get("name") or "").lower()
        matching_subs = [s for s in subs if q in (s.get("name") or "").lower()]
        if not root_match and not matching_subs:
            continue
        if root_match:
            result.append({**item, "subs": subs})
        else:
            result.append({**item, "subs": matching_subs})
    return result
