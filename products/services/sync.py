from __future__ import annotations

import logging
from typing import Any

from django.core.cache import cache
from django.db import IntegrityError, transaction

from products.models import Category
from products.repositories import CategoryRepository, ProductRepository


class CategorySyncService:
    @staticmethod
    def sync_batch(items: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Учитывает parent_id: сначала корни, затем дочерние (несколько проходов).
        Уже существующие в БД родители учитываются.
        """
        created = 0
        updated = 0
        seen: set[str] = {str(pk) for pk in Category.objects.values_list("id", flat=True)}
        pending = list(items)
        max_rounds = max(len(items), 1) + 5
        with transaction.atomic():
            for _ in range(max_rounds):
                if not pending:
                    break
                nxt: list[dict[str, Any]] = []
                progressed = False
                for raw in pending:
                    pid = raw.get("parent_id")
                    parent_ok = pid is None or str(pid).strip() == "" or str(pid).strip() in seen
                    if not parent_ok:
                        nxt.append(raw)
                        continue
                    _, was_created = CategoryRepository.upsert_from_payload(raw)
                    if was_created:
                        created += 1
                    else:
                        updated += 1
                    seen.add(str(raw["id"]).strip())
                    progressed = True
                if not progressed and nxt:
                    for raw in nxt:
                        raw2 = dict(raw)
                        raw2["parent_id"] = None
                        _, was_created = CategoryRepository.upsert_from_payload(raw2)
                        if was_created:
                            created += 1
                        else:
                            updated += 1
                        seen.add(str(raw["id"]).strip())
                    break
                pending = nxt
            if pending:
                for raw in pending:
                    raw2 = dict(raw)
                    raw2["parent_id"] = None
                    _, was_created = CategoryRepository.upsert_from_payload(raw2)
                    if was_created:
                        created += 1
                    else:
                        updated += 1
        cache.delete("shop:category_groups:catalog")
        cache.delete("shop:category_groups:demo")
        return {"created": created, "updated": updated, "total": len(items)}


logger = logging.getLogger(__name__)

ONEC_LAST_PRODUCT_LIST_COUNT_CACHE_KEY = "shop:onec_last_product_list_count"
_ONEC_LAST_PRODUCT_LIST_COUNT_TTL = 60 * 60 * 24 * 7


class ProductSyncService:
    @staticmethod
    def sync_batch(items: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Товары ссылаются на category_id из справочника категорий.
        Если в ответе productList есть ссылка на отсутствующую категорию — строка пропускается (SQLite FK).
        Категории задаются деревом categoryProductList (N-*); при ``ONEC_LEGACY_CATEGORY_LIST_FALLBACK`` — добор из categoryList.
        """
        valid_cats = {str(x) for x in Category.objects.values_list("id", flat=True)}
        created = 0
        updated = 0
        skipped = 0
        for raw in items:
            cid = str(raw.get("category_id", "") or "").strip()
            pid = str(raw.get("id", "") or "").strip()
            if not cid:
                skipped += 1
                logger.debug("Product %s: пропуск, нет category_id", pid)
                continue
            if cid not in valid_cats:
                skipped += 1
                if skipped <= 20:
                    logger.warning(
                        "Товар %s: пропуск, неизвестная категория %s (нет среди синхронизированных категорий)",
                        pid,
                        cid,
                    )
                continue
            try:
                with transaction.atomic():
                    _, was_created = ProductRepository.upsert_from_payload(raw)
                if was_created:
                    created += 1
                else:
                    updated += 1
            except IntegrityError as exc:
                skipped += 1
                logger.warning("Товар %s: пропуск из-за IntegrityError: %s", pid, exc)
        out = {"created": created, "updated": updated, "skipped": skipped, "total": len(items)}
        if skipped:
            logger.warning("Синхронизация товаров: пропущено строк: %s", skipped)
        cache.delete("shop:catalog_products_exist")
        return out

    @staticmethod
    def reconcile_missing_from_onec(onec_product_ids: set[str]) -> dict[str, Any]:
        """
        Деактивировать товары в БД, которых больше нет в ответе GET productList.

        Вызывается только после успешной загрузки полного списка из 1С
        (``integrations.services.onec_full_sync``), не при ручном POST sync.
        """
        from django.conf import settings

        from products.models import Product

        if not getattr(settings, "ONEC_SYNC_DEACTIVATE_MISSING_PRODUCTS", True):
            return {"deactivated": 0, "skipped": True, "reason": "disabled"}

        onec_ids = {str(x).strip() for x in onec_product_ids if str(x).strip()}
        if not onec_ids:
            logger.warning(
                "reconcile_missing_from_onec: пустой productList — деактивация пропущена"
            )
            return {"deactivated": 0, "skipped": True, "reason": "empty_product_list"}

        min_ratio = float(getattr(settings, "ONEC_SYNC_RECONCILE_MIN_COUNT_RATIO", 0.5))
        prev_count = cache.get(ONEC_LAST_PRODUCT_LIST_COUNT_CACHE_KEY)
        if prev_count is not None and len(onec_ids) < int(prev_count) * min_ratio:
            logger.error(
                "reconcile_missing_from_onec: подозрительное падение числа товаров "
                "%s → %s (порог %.0f%%) — деактивация пропущена",
                prev_count,
                len(onec_ids),
                min_ratio * 100,
            )
            return {
                "deactivated": 0,
                "skipped": True,
                "reason": "suspicious_count_drop",
                "previous_count": int(prev_count),
                "current_count": len(onec_ids),
            }

        cache.set(
            ONEC_LAST_PRODUCT_LIST_COUNT_CACHE_KEY,
            len(onec_ids),
            _ONEC_LAST_PRODUCT_LIST_COUNT_TTL,
        )

        qs = Product.objects.filter(is_active=True).exclude(id__in=onec_ids)
        deactivated_ids = list(qs.values_list("id", flat=True))
        count = len(deactivated_ids)
        if count:
            qs.update(is_active=False)
            logger.info(
                "reconcile_missing_from_onec: деактивировано %s товаров (нет в productList)",
                count,
            )
            sample = deactivated_ids[:20]
            if count <= 20:
                logger.info("deactivated ids: %s", sample)
            else:
                logger.info("deactivated ids (first 20): %s …", sample)

        cache.delete("shop:catalog_products_exist")
        return {
            "deactivated": count,
            "skipped": False,
            "deactivated_ids_sample": deactivated_ids[:20],
        }
