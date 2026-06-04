"""
Разбор GET .../categories_products/categoryProductList.

Поддерживаются два формата ответа 1С:
1) Массив объектов вида {"id", "name", "products": [...]} — товары в products могут быть
   строками (наименование) или объектами с полем name/id.
2) Объект с одним корневым ключом и вложенными категориями; в листьях — строки наименований
   (текущая публикация bereke).

Категории для БД: стабильные id N-<hash> по пути в дереве (формат 2) или id из API (формат 1).
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

CATEGORY_TREE_ROOT_ORDER_CACHE_KEY = "shop:category_tree_root_order"

_WS = re.compile(r"\s+")


def normalize_product_name_key(name: str) -> str:
    s = (name or "").strip()
    s = _WS.sub(" ", s)
    return s.casefold()


def _segment_id(path_segments: tuple[str, ...]) -> str:
    raw = " › ".join(s.strip() for s in path_segments if s and s.strip())
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return f"N-{h}"


def _visit_value(
    value: Any,
    parent_id: str | None,
    path: tuple[str, ...],
    categories_out: list[dict[str, Any]],
    name_map_out: dict[str, str],
) -> None:
    if isinstance(value, dict):
        _walk_dict(value, parent_id, path, categories_out, name_map_out)
        return
    if isinstance(value, list):
        for el in value:
            if isinstance(el, str):
                nk = normalize_product_name_key(el)
                if nk and parent_id:
                    if nk in name_map_out and name_map_out[nk] != parent_id:
                        logger.debug("Дубликат названия в дереве: %r", el[:80])
                    name_map_out[nk] = parent_id
            else:
                _visit_value(el, parent_id, path, categories_out, name_map_out)


def _walk_dict(
    d: dict[str, Any],
    parent_id: str | None,
    path: tuple[str, ...],
    categories_out: list[dict[str, Any]],
    name_map_out: dict[str, str],
) -> None:
    for k_raw, v in d.items():
        k = (k_raw or "").strip()
        if not k:
            continue
        my_path = path + (k,)
        cid = _segment_id(my_path)
        categories_out.append(
            {
                "id": cid,
                "name": k,
                "parent_id": parent_id,
                "is_active": True,
            }
        )
        _visit_value(v, cid, my_path, categories_out, name_map_out)


def _parse_flat_category_blocks(data: list[Any]) -> tuple[list[dict[str, Any]], dict[str, str], list[str]]:
    """Формат: [{ "id", "name", "products": [...] }, ...]."""
    categories: list[dict[str, Any]] = []
    name_map: dict[str, str] = {}
    root_ids: list[str] = []

    for item in data:
        if not isinstance(item, dict):
            continue
        cid = str(item.get("id", "") or "").strip()
        name = str(item.get("name", "") or "").strip()
        if not cid or not name:
            continue
        categories.append(
            {
                "id": cid,
                "name": name,
                "parent_id": None,
                "is_active": bool(item.get("is_active", True)),
            }
        )
        root_ids.append(cid)
        for p in item.get("products") or []:
            if isinstance(p, str):
                nk = normalize_product_name_key(p)
                if nk:
                    name_map[nk] = cid
            elif isinstance(p, dict):
                pname = p.get("name") or p.get("title") or p.get("presentation") or ""
                nk = normalize_product_name_key(str(pname))
                if nk:
                    name_map[nk] = cid

    return categories, name_map, root_ids


def _parse_nested_site_tree(data: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, str], list[str]]:
    categories: list[dict[str, Any]] = []
    name_map: dict[str, str] = {}
    root_ids: list[str] = []

    root_val = next(iter(data.values()))
    if not isinstance(root_val, list):
        logger.warning("categoryProductList: под корневым ключом ожидался список")
        return categories, name_map, root_ids

    for block in root_val:
        if isinstance(block, dict):
            before = len(categories)
            _walk_dict(block, None, (), categories, name_map)
            if len(categories) > before:
                root_ids.append(str(categories[before]["id"]))

    return categories, name_map, root_ids


def _looks_flat_category_row(d: dict[str, Any]) -> bool:
    """Строка вида {id, name, products?} — не путать с блоком {«Школа»: [...]}."""
    if "products" in d:
        return True
    return "id" in d and "name" in d


def parse_category_product_payload(data: Any) -> tuple[list[dict[str, Any]], dict[str, str], list[str]]:
    """
    Унифицированный разбор categoryProductList.

    Возвращает:
    - rows для CategorySyncService;
    - карту нормализованное_имя_товара -> category_id;
    - порядок id корневых категорий (для меню и витрины).
    """
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict) and _looks_flat_category_row(first):
            return _parse_flat_category_blocks(data)
        logger.warning(
            "categoryProductList: получен список без полей id/name/products у первого элемента — ожидается объект-корень"
        )

    if isinstance(data, dict) and data:
        return _parse_nested_site_tree(data)

    return [], {}, []


# Обратная совместимость с прежним именем
def parse_category_product_list_payload(data: Any) -> tuple[list[dict[str, Any]], dict[str, str], list[str]]:
    return parse_category_product_payload(data)
