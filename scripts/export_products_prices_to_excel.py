"""Экспорт товаров в порядке categoryProductList с ценами в MS Excel (.xlsx).

Источник данных:
- GET /categories_products/categoryProductList -> порядок товаров
- GET /products/productList -> розничная и оптовая цены

Запуск:
    ./venv/Scripts/python.exe scripts/export_products_prices_to_excel.py
"""

from __future__ import annotations

import argparse
import base64
import os
import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from openpyxl import Workbook

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from integrations.onec_constants import ONEC_DEFAULT_BASE_URL  # noqa: E402

PATH_CATEGORY_PRODUCT_LIST = "/categories_products/categoryProductList"
PATH_PRODUCT_LIST = "/products/productList"
_WS_RE = re.compile(r"\s+")


def normalize_name(name: str) -> str:
    s = (name or "").strip()
    s = _WS_RE.sub(" ", s)
    return s.casefold()


def _to_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    try:
        s = str(value).strip().replace(" ", "").replace("\xa0", "")
        if "," in s and "." in s:
            s = s.replace(",", "")
        elif "," in s and "." not in s:
            s = s.replace(",", ".")
        return Decimal(s)
    except (InvalidOperation, ValueError, TypeError):
        return None


def _extract_retail_wholesale(data: dict[str, Any]) -> tuple[Decimal | None, Decimal | None]:
    raw_prices = data.get("prices")
    retail: Decimal | None = None
    wholesale: Decimal | None = None

    if isinstance(raw_prices, dict):
        for key in ("retail", "Retail", "priceRetail", "PriceRetail", "розница", "Розница"):
            if key in raw_prices and raw_prices[key] is not None:
                retail = _to_decimal(raw_prices[key])
                break
        for key in ("wholesale", "Wholesale", "priceWholesale", "PriceWholesale", "опт", "Опт"):
            if key in raw_prices and raw_prices[key] is not None:
                wholesale = _to_decimal(raw_prices[key])
                break
    elif isinstance(raw_prices, list):
        for item in raw_prices:
            if not isinstance(item, dict):
                continue
            t = str(item.get("type") or item.get("kind") or item.get("name") or "").strip().lower()
            v = item.get("value", item.get("price"))
            if v is None:
                continue
            if retail is None and ("розниц" in t or "retail" in t or t in ("р", "розница")):
                retail = _to_decimal(v)
            if wholesale is None and ("опт" in t or "wholesale" in t or "wholesal" in t):
                wholesale = _to_decimal(v)

    if retail is None:
        retail = _to_decimal(data.get("retail_price"))
    if wholesale is None:
        wholesale = _to_decimal(data.get("wholesale_price"))

    return retail, wholesale


def collect_product_names_in_order(payload: Any) -> list[str]:
    ordered_names: list[str] = []

    def visit(node: Any) -> None:
        if isinstance(node, str):
            nm = node.strip()
            if nm:
                ordered_names.append(nm)
            return
        if isinstance(node, list):
            for item in node:
                visit(item)
            return
        if isinstance(node, dict):
            for _, value in node.items():
                visit(value)

    visit(payload)
    return ordered_names


def build_headers() -> dict[str, str]:
    headers: dict[str, str] = {
        "Accept": "application/json",
        "Content-Type": "application/json; charset=utf-8",
        "X-Source": os.getenv("ONEC_API_SOURCE", "website"),
    }

    auth_raw = (os.getenv("ONEC_API_BASIC_AUTH") or "").strip()
    if auth_raw:
        headers["Authorization"] = auth_raw if auth_raw.startswith("Basic ") else f"Basic {auth_raw}"
        return headers

    basic_user = (os.getenv("ONEC_API_BASIC_USER") or "").strip()
    basic_password = (os.getenv("ONEC_API_BASIC_PASSWORD") or "").strip()
    if basic_user or basic_password:
        b64 = base64.b64encode(f"{basic_user}:{basic_password}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {b64}"
        return headers

    token = (os.getenv("ONEC_API_TOKEN") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    return headers


def fetch_json(path: str, timeout: float, verify_ssl: bool) -> Any:
    base_url = (os.getenv("ONEC_API_BASE_URL") or "").rstrip("/")
    if not base_url:
        base_url = ONEC_DEFAULT_BASE_URL
    url = f"{base_url}{path}"

    with httpx.Client(timeout=timeout, verify=verify_ssl) as client:
        response = client.get(url, headers=build_headers())
        response.raise_for_status()
        return response.json()


def build_price_map(products_payload: Any) -> dict[str, tuple[Decimal | None, Decimal | None]]:
    if not isinstance(products_payload, list):
        raise ValueError("Ожидается JSON-массив от /products/productList")

    grouped: dict[str, list[tuple[Decimal | None, Decimal | None]]] = defaultdict(list)
    for row in products_payload:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        grouped[normalize_name(name)].append(_extract_retail_wholesale(row))

    # При дубликатах названий берём первую запись по порядку от API.
    return {k: v[0] for k, v in grouped.items() if v}


def export_to_excel(
    product_names_in_order: list[str],
    price_map: dict[str, tuple[Decimal | None, Decimal | None]],
    out_path: Path,
) -> tuple[int, int]:
    wb = Workbook()
    ws = wb.active
    ws.title = "Товары и цены"
    ws.append(["№", "Товар", "Оптовая цена", "Розничная цена"])

    resolved = 0
    for idx, name in enumerate(product_names_in_order, start=1):
        retail, wholesale = price_map.get(normalize_name(name), (None, None))
        if retail is not None or wholesale is not None:
            resolved += 1
        ws.append(
            [
                idx,
                name,
                float(wholesale) if wholesale is not None else "",
                float(retail) if retail is not None else "",
            ]
        )

    ws.column_dimensions["A"].width = 8
    ws.column_dimensions["B"].width = 80
    ws.column_dimensions["C"].width = 18
    ws.column_dimensions["D"].width = 18

    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    return len(product_names_in_order), resolved


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Экспорт товаров с оптовой и розничной ценой в Excel (.xlsx)."
    )
    parser.add_argument(
        "--output",
        default="exports/products_prices.xlsx",
        help="Путь выходного .xlsx файла (по умолчанию: exports/products_prices.xlsx)",
    )
    args = parser.parse_args()

    verify_ssl = (os.getenv("ONEC_VERIFY_SSL", "true").strip().lower() in ("1", "true", "yes"))
    timeout = float(os.getenv("ONEC_API_TIMEOUT", "120"))

    category_tree_payload = fetch_json(PATH_CATEGORY_PRODUCT_LIST, timeout=timeout, verify_ssl=verify_ssl)
    product_names_in_order = collect_product_names_in_order(category_tree_payload)
    products_payload = fetch_json(PATH_PRODUCT_LIST, timeout=timeout, verify_ssl=verify_ssl)
    price_map = build_price_map(products_payload)

    total, resolved = export_to_excel(
        product_names_in_order=product_names_in_order,
        price_map=price_map,
        out_path=ROOT / args.output,
    )

    print(f"Сохранено: {args.output}")
    print(f"Товаров в порядке categoryProductList: {total}")
    print(f"Найдено цен в productList: {resolved}")


if __name__ == "__main__":
    main()
