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
