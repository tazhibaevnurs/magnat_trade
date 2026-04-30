"""Дерево категорий для меню и API поиска в выпадающем каталоге."""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q

from integrations.parsers.category_product_tree import CATEGORY_TREE_ROOT_ORDER_CACHE_KEY

from .models import Category

logger = logging.getLogger(__name__)


def normalize_nav_root_title(name: str) -> str:
    """Сопоставление подписей из .env и названий из 1С (пробелы, точки в конце)."""
    s = (name or "").strip()
    s = re.sub(r"\s+", " ", s)
    while len(s) > 1 and s[-1] in ".…,;":
        s = s[:-1].strip()
    return s.casefold()


def _match_nav_roots_by_allowlist(
    roots: list[Any],
    ordered_labels: list[str],
) -> list[Any]:
    """Упорядочивает корни по списку имён; пропускает отсутствующие с предупреждением в лог."""
    by_norm = {normalize_nav_root_title(getattr(r, "name", "") or ""): r for r in roots}
    out: list[Any] = []
    for label in ordered_labels:
        key = normalize_nav_root_title(label)
        obj = by_norm.get(key)
        if obj is not None:
            out.append(obj)
        else:
            logger.warning(
                "SHOP_NAV_ROOT_CATEGORY_NAMES: корень не найден в БД по названию «%s»",
                label[:120],
            )
    return out


def _tree_ids_under_product_roots(root_pcs: list[Any]) -> set[str]:
    """Все id categories.Product в поддеревьях данных корней."""
    ids: set[str] = set()
    frontier = list(root_pcs)
    from products.models import Category as ProductCategory

    while frontier:
        pc = frontier.pop()
        cid = str(getattr(pc, "pk", "") or "")
        if not cid or cid in ids:
            continue
        ids.add(cid)
        for ch in ProductCategory.objects.filter(parent_id=cid).only("id"):
            frontier.append(ch)
    return ids


def _product_catalog_roots_ordered():
    """Корни дерева N-* в порядке из categoryProductList (кэш) либо по имени."""
    from products.models import Category as ProductCategory

    order = cache.get(CATEGORY_TREE_ROOT_ORDER_CACHE_KEY)
    pc_roots: list = []
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
    return pc_roots


def _nav_allowlist_resolve(pc_roots: list[Any]) -> tuple[list[Any], frozenset[str] | None]:
    """Возвращает корни для меню и id дерева категорий для фильтра slug; restrict=None — без ограничения."""
    nav_names = getattr(settings, "SHOP_NAV_ROOT_CATEGORY_NAMES", []) or []
    if not nav_names:
        return pc_roots, None
    matched = _match_nav_roots_by_allowlist(pc_roots, nav_names)
    if not matched:
        logger.warning(
            "SHOP_NAV_ROOT_CATEGORY_NAMES: ни один корень не совпал с ответом 1С / БД — фильтр разделов отключён",
        )
        return pc_roots, None
    return matched, frozenset(_tree_ids_under_product_roots(matched))


def get_catalog_roots_for_admin_display():
    """Корневые категории каталога 1С (products.Category) в том же порядке, что и в меню сайта."""
    from products.models import Category as ProductCategory

    if not ProductCategory.objects.filter(id__startswith="N-").exists():
        return list(ProductCategory.objects.filter(parent__isnull=True).order_by("name"))
    pc_roots = _product_catalog_roots_ordered()
    resolved, _restrict = _nav_allowlist_resolve(pc_roots)
    return resolved


def catalog_nav_restricted_tree_ids() -> frozenset[str] | None:
    """Для группировки категорий на витрине: ограничение поддеревом allowlist или None."""
    from products.models import Category as ProductCategory

    if not ProductCategory.objects.filter(id__startswith="N-").exists():
        return None
    _, restrict = _nav_allowlist_resolve(_product_catalog_roots_ordered())
    return restrict


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

    pc_roots = _product_catalog_roots_ordered()
    pc_roots, restrict_ids = _nav_allowlist_resolve(pc_roots)

    roots: list[Category] = []
    for pc in pc_roots:
        sc = (
            Category.objects.filter(slug=pc.slug, parent__isnull=True)
            .prefetch_related("children")
            .first()
        )
        if sc:
            roots.append(sc)

    if restrict_ids is not None:
        allowed = set(
            ProductCategory.objects.filter(pk__in=restrict_ids).values_list("slug", flat=True)
        )
    else:
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

    pc_roots = _product_catalog_roots_ordered()
    pc_roots, _restrict = _nav_allowlist_resolve(pc_roots)
    return pc_roots


def _shop_category_descendant_pks(roots: list[Category]) -> set[int]:
    """Все shop.Category.pk в поддеревьях переданных корней (включая сами корни)."""
    ids: set[int] = set()
    frontier = [int(r.pk) for r in roots]
    while frontier:
        pk = frontier.pop()
        if pk in ids:
            continue
        ids.add(pk)
        frontier.extend(Category.objects.filter(parent_id=pk).values_list("pk", flat=True))
    return ids


def build_category_nav_payload(
    roots: list[Category] | None = None,
    *,
    allowed_descendant_slugs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Полное дерево под каждым корнем (не только прямые дочерние), как в JSON categoryProductList.

    Каждый узел: ``slug``, ``name``, ``subs`` — список таких же узлов (рекурсивно).
    """
    if roots is None:
        roots = list(Category.objects.filter(parent__isnull=True).order_by("name"))

    if not roots:
        return []

    desc_ids = _shop_category_descendant_pks(roots)
    qs = Category.objects.filter(pk__in=desc_ids).order_by("name")
    if allowed_descendant_slugs is not None:
        root_pk_set = {int(r.pk) for r in roots}
        qs = qs.filter(Q(slug__in=allowed_descendant_slugs) | Q(pk__in=root_pk_set))

    cats = list(qs)
    by_parent: dict[int | None, list[Category]] = defaultdict(list)
    for c in cats:
        by_parent[c.parent_id].append(c)

    for lst in by_parent.values():
        lst.sort(key=lambda x: x.name)

    def walk(cat: Category) -> dict[str, Any]:
        children = by_parent.get(cat.pk, [])
        return {"slug": cat.slug, "name": cat.name, "subs": [walk(ch) for ch in children]}

    return [walk(r) for r in roots]


def filter_category_nav(payload: list[dict[str, Any]], q: str) -> list[dict[str, Any]]:
    qn = (q or "").strip().lower()
    if not qn:
        return payload

    def filt(node: dict[str, Any]) -> dict[str, Any] | None:
        name_l = (node.get("name") or "").lower()
        subs_in = node.get("subs") or []
        filtered_children: list[dict[str, Any]] = []
        for s in subs_in:
            fs = filt(s)
            if fs is not None:
                filtered_children.append(fs)
        if qn in name_l:
            return {**node, "subs": subs_in}
        if filtered_children:
            return {**node, "subs": filtered_children}
        return None

    out: list[dict[str, Any]] = []
    for item in payload:
        fi = filt(item)
        if fi is not None:
            out.append(fi)
    return out


def ancestor_shop_category_slugs_for_selection(selected_slugs: list[str]) -> set[str]:
    """Цепочка slug от выбранных категорий вверх до корня — для раскрытия вложенных веток в меню."""
    out: set[str] = set()
    for slug in selected_slugs:
        slug = (slug or "").strip()
        if not slug:
            continue
        c = Category.objects.filter(slug=slug).only("slug", "parent_id").first()
        while c:
            out.add(c.slug)
            c = c.parent
    return out
