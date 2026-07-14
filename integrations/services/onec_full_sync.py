"""Полная синхронизация справочников из 1С в локальную БД.

GET каталога:
- categories_products/categoryProductList (дерево категорий N-* и сопоставление товаров по наименованию)
- products/productList (номенклатура, цены, остатки; category_id из 1С перезаписывается по дереву при совпадении имени)
- при ``ONEC_LEGACY_CATEGORY_LIST_FALLBACK`` — categories/categoryList только для недостающих кодов категорий
- counterparties/counterpartyList (опционально)

Используется в ``manage.py sync_onec``, Celery ``sync_all_from_onec`` и ``POST /api/v1/onec/sync-full/``.
"""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.core.cache import cache

from integrations.clients.onec import (
    PATH_CATEGORY_LIST,
    PATH_CATEGORY_PRODUCT_LIST,
    PATH_COUNTERPARTY_LIST,
    PATH_PRODUCT_LIST,
    OneCAPIError,
    OneCClient,
)
from integrations.parsers.category_product_tree import (
    CATEGORY_TREE_ROOT_ORDER_CACHE_KEY,
    normalize_product_name_key,
    parse_category_product_payload,
)
from products.models import Category
from products.services import CategorySyncService, ProductSyncService
from shop.services.category_mirror import mirror_products_categories_to_shop
from users.services import CustomerSyncService

logger = logging.getLogger(__name__)

CATEGORY_PRODUCT_NAME_MAP_CACHE_KEY = "shop:onec_category_product_name_map"
_CATEGORY_NAME_MAP_CACHE_TTL = 60 * 60 * 24 * 7


def _apply_category_tree_to_products(
    items: list[dict[str, Any]],
    name_map: dict[str, str],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in items:
        r = dict(raw)
        nk = normalize_product_name_key(str(r.get("name") or ""))
        if nk and nk in name_map:
            r["category_id"] = name_map[nk]
        out.append(r)
    return out


def _sync_legacy_categories_for_missing_ids(
    client: OneCClient,
    products_payload: list[dict[str, Any]],
) -> dict[str, Any]:
    if not getattr(settings, "ONEC_LEGACY_CATEGORY_LIST_FALLBACK", False):
        return {
            "skipped": True,
            "reason": "ONEC_LEGACY_CATEGORY_LIST_FALLBACK is disabled",
        }
    existing = {str(x) for x in Category.objects.values_list("id", flat=True)}
    needed: set[str] = set()
    for raw in products_payload:
        cid = str(raw.get("category_id", "") or "").strip()
        if cid:
            needed.add(cid)
    missing = sorted(needed - existing)
    if not missing:
        return {"skipped": True, "missing_count": 0}
    logger.info("1С: для %s категорий без дерева — GET %s", len(missing), PATH_CATEGORY_LIST)
    legacy = client.fetch_category_list()
    miss_set = set(missing)
    subset = [x for x in legacy if str(x.get("id", "") or "").strip() in miss_set]
    if len(subset) < len(missing):
        logger.warning(
            "categoryList: найдено %s из %s недостающих категорий по id",
            len(subset),
            len(missing),
        )
    return CategorySyncService.sync_batch(subset)


def _load_name_map_for_product_sync(client: OneCClient) -> dict[str, str]:
    cached = cache.get(CATEGORY_PRODUCT_NAME_MAP_CACHE_KEY)
    if isinstance(cached, dict) and cached:
        return cached
    raw = client.fetch_category_product_list()
    _, name_map, root_order = parse_category_product_payload(raw)
    cache.set(CATEGORY_PRODUCT_NAME_MAP_CACHE_KEY, name_map, _CATEGORY_NAME_MAP_CACHE_TTL)
    cache.set(CATEGORY_TREE_ROOT_ORDER_CACHE_KEY, root_order, _CATEGORY_NAME_MAP_CACHE_TTL)
    return name_map


def _sync_products_with_name_map(
    client: OneCClient,
    name_map: dict[str, str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    logger.info("1С: products GET %s", PATH_PRODUCT_LIST)
    prods = client.fetch_product_list()
    onec_ids = {
        str(raw.get("id", "") or "").strip()
        for raw in prods
        if str(raw.get("id", "") or "").strip()
    }
    mapped = _apply_category_tree_to_products(prods, name_map)
    legacy = _sync_legacy_categories_for_missing_ids(client, mapped)
    result = ProductSyncService.sync_batch(mapped)
    result["reconcile"] = ProductSyncService.reconcile_missing_from_onec(onec_ids)
    cache.delete("shop:catalog_products_exist")
    return legacy, result


def sync_products_batch_from_onec_client(client: OneCClient) -> dict[str, Any]:
    name_map = _load_name_map_for_product_sync(client)
    _, batch = _sync_products_with_name_map(client, name_map)
    return batch


def run_product_list_sync_only() -> dict[str, Any]:
    base = (getattr(settings, "ONEC_API_BASE_URL", "") or "").strip()
    if not base:
        return {
            "ok": False,
            "skipped": True,
            "reason": "ONEC_API_BASE_URL is not configured",
        }
    client = OneCClient()
    batch = sync_products_batch_from_onec_client(client)
    return {
        "ok": True,
        "onec_urls_requested": [
            f"{base.rstrip('/')}{PATH_CATEGORY_PRODUCT_LIST}",
            f"{base.rstrip('/')}{PATH_PRODUCT_LIST}",
        ],
        "products": batch,
    }


def onec_sync_get_urls(*, skip_customers: bool = False) -> list[str]:
    base = (getattr(settings, "ONEC_API_BASE_URL", "") or "").strip().rstrip("/")
    if not base:
        return []
    paths = [PATH_CATEGORY_PRODUCT_LIST, PATH_PRODUCT_LIST]
    if not skip_customers:
        paths.append(PATH_COUNTERPARTY_LIST)
    return [f"{base}{p}" for p in paths]


def run_full_onec_sync(*, skip_customers: bool = False) -> dict[str, Any]:
    base = (getattr(settings, "ONEC_API_BASE_URL", "") or "").strip()
    if not base:
        return {
            "ok": False,
            "skipped": True,
            "reason": "ONEC_API_BASE_URL is not configured",
        }

    client = OneCClient()
    out: dict[str, Any] = {
        "ok": True,
        "onec_urls_requested": onec_sync_get_urls(skip_customers=skip_customers),
    }

    logger.info("1С full sync: categories+tree GET %s", PATH_CATEGORY_PRODUCT_LIST)
    tree_payload = client.fetch_category_product_list()
    cat_rows, name_map, root_order = parse_category_product_payload(tree_payload)
    cache.set(CATEGORY_PRODUCT_NAME_MAP_CACHE_KEY, name_map, _CATEGORY_NAME_MAP_CACHE_TTL)
    cache.set(CATEGORY_TREE_ROOT_ORDER_CACHE_KEY, root_order, _CATEGORY_NAME_MAP_CACHE_TTL)
    out["categories"] = CategorySyncService.sync_batch(cat_rows)
    out["category_product_tree"] = {
        "categories_total": len(cat_rows),
        "product_name_map_size": len(name_map),
        "root_count": len(root_order),
    }

    logger.info("1С full sync: mirror shop categories")
    out["mirror_shop_categories"] = mirror_products_categories_to_shop()

    legacy, prod_batch = _sync_products_with_name_map(client, name_map)
    out["legacy_categories"] = legacy
    out["products"] = prod_batch

    if not skip_customers:
        logger.info("1С full sync: counterparties GET %s", PATH_COUNTERPARTY_LIST)
        cust = client.fetch_counterparty_list()
        out["customers"] = CustomerSyncService.sync_batch(cust)
    else:
        out["customers"] = {"skipped": True}

    return out
