"""Группировка категорий витрины по родителю (разделы каталога из 1С)."""

from __future__ import annotations

from typing import Any, Callable

from django.core.cache import cache

from integrations.parsers.category_product_tree import CATEGORY_TREE_ROOT_ORDER_CACHE_KEY

_CACHE_PREFIX = "shop:category_groups"
_CACHE_TTL = 300


def _tree_category_ids() -> set[str] | None:
    """Категории из categoryProductList (N-*); None — нового дерева ещё нет."""
    from products.models import Category as CatalogCategory

    ids = list(CatalogCategory.objects.filter(id__startswith="N-").values_list("id", flat=True))
    return set(ids) if ids else None


def _group_by_parent(
    cats: list,
    has_products_in_category: Callable[[Any], bool],
    *,
    root_order: list[str] | None = None,
) -> list[dict[str, Any]]:
    by_parent: dict[Any, list] = {}
    for c in cats:
        by_parent.setdefault(c.parent_id, []).append(c)

    raw_roots = by_parent.get(None, []) or []
    if root_order:
        order_index = {rid: i for i, rid in enumerate(root_order)}
        roots = sorted(raw_roots, key=lambda x: (order_index.get(x.id, 10_000), x.name))
    else:
        roots = sorted(raw_roots, key=lambda x: x.name)

    if not roots:
        return [
            {
                "title": "Категории",
                "items": [(c.slug, c.name) for c in sorted(cats, key=lambda x: x.name)],
            }
        ]

    if not any(by_parent.get(r.id, []) for r in roots):
        return [
            {
                "title": "Категории",
                "items": [(c.slug, c.name) for c in roots],
            }
        ]

    groups: list[dict[str, Any]] = []
    assigned: set[Any] = set()

    for root in roots:
        subs = sorted(by_parent.get(root.id, []), key=lambda x: x.name)
        if subs:
            items: list[tuple[str, str]] = []
            if has_products_in_category(root.id):
                items.append((root.slug, root.name))
            items.extend((s.slug, s.name) for s in subs)
            groups.append({"title": root.name, "items": items})
            assigned.add(root.id)
            assigned.update(s.id for s in subs)
        else:
            groups.append({"title": root.name, "items": [(root.slug, root.name)]})
            assigned.add(root.id)

    remaining = [c for c in cats if c.id not in assigned]
    if remaining:
        groups.append(
            {
                "title": "Другие категории",
                "items": [(c.slug, c.name) for c in sorted(remaining, key=lambda x: x.name)],
            }
        )

    return groups


def build_category_groups(*, catalog_mode: bool) -> list[dict[str, Any]]:
    if catalog_mode:
        from products.models import Category as CatalogCategory
        from products.models import Product as CatalogProduct

        tree_ids = _tree_category_ids()
        qs = CatalogCategory.objects.filter(is_active=True).select_related("parent")
        if tree_ids is not None:
            qs = qs.filter(id__in=tree_ids)
        cats = list(qs.order_by("name"))

        root_order = cache.get(CATEGORY_TREE_ROOT_ORDER_CACHE_KEY)
        if not isinstance(root_order, list) or not root_order:
            root_order = None
        else:
            root_order = [str(x) for x in root_order]

        def has_products(cat_id: Any) -> bool:
            return CatalogProduct.objects.filter(is_active=True, category_id=cat_id).exists()

    else:
        from shop.models import Category as ShopCategory
        from shop.models import Product as ShopProduct

        cats = list(ShopCategory.objects.select_related("parent").order_by("name"))
        root_order = None

        def has_products(cat_id: Any) -> bool:
            return ShopProduct.objects.filter(is_active=True, category_id=cat_id).exists()

    if not cats:
        return []

    if catalog_mode:
        return _group_by_parent(cats, has_products, root_order=root_order)
    return _group_by_parent(cats, has_products)


def cached_category_groups(*, catalog_mode: bool) -> list[dict[str, Any]]:
    key = f"{_CACHE_PREFIX}:{'catalog' if catalog_mode else 'demo'}"

    def _fetch() -> list[dict[str, Any]]:
        return build_category_groups(catalog_mode=catalog_mode)

    return cache.get_or_set(key, _fetch, _CACHE_TTL)
