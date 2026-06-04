"""Проверка доступности всех URL HTTP-сервиса 1С."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Callable

from integrations.clients.onec import (
    ONEC_SYNC_CATALOG_GET_PATHS,
    PATH_CATEGORY_LIST,
    PATH_CATEGORY_PRODUCT_LIST,
    PATH_COUNTERPARTY_LIST,
    PATH_CREATE_COUNTERPARTY,
    PATH_CREATE_ORDER,
    PATH_PRODUCT_LIST,
    OneCAPIError,
    OneCClient,
)
from integrations.services.onec_registration import build_create_counterparty_payload


@dataclass
class OneCEndpointSpec:
    path: str
    method: str
    label: str
    mutating: bool = False


ONEC_SMOKE_GET_ENDPOINTS: tuple[OneCEndpointSpec, ...] = (
    OneCEndpointSpec(PATH_COUNTERPARTY_LIST, "GET", "counterpartyList"),
    OneCEndpointSpec(PATH_CATEGORY_LIST, "GET", "categoryList"),
    OneCEndpointSpec(PATH_CATEGORY_PRODUCT_LIST, "GET", "categoryProductList"),
    OneCEndpointSpec(PATH_PRODUCT_LIST, "GET", "productList"),
)

ONEC_SMOKE_POST_ENDPOINTS: tuple[OneCEndpointSpec, ...] = (
    OneCEndpointSpec(PATH_CREATE_COUNTERPARTY, "POST", "create_counterparty", mutating=True),
    OneCEndpointSpec(PATH_CREATE_ORDER, "POST", "createOrder", mutating=True),
)


@dataclass
class OneCSmokeResult:
    path: str
    method: str
    label: str
    url: str
    ok: bool
    status_code: int | None = None
    duration_ms: int | None = None
    detail: str = ""
    skipped: bool = False


@dataclass
class OneCSmokeReport:
    base_url: str
    results: list[OneCSmokeResult] = field(default_factory=list)

    @property
    def all_ok(self) -> bool:
        return all(r.ok or r.skipped for r in self.results)

    @property
    def failed(self) -> list[OneCSmokeResult]:
        return [r for r in self.results if not r.ok and not r.skipped]


def _sample_create_counterparty_payload() -> dict[str, Any]:
    """Тот же контракт, что при регистрации на сайте (1С требует is_active в JSON)."""
    suffix = uuid.uuid4().hex[:12]
    user = SimpleNamespace(
        pk=0,
        first_name="Smoke",
        last_name="Test",
        email=f"smoke-{suffix}@example.test",
        phone="+996700000000",
        entity_type="individual",
        user_type="retail",
    )
    payload = build_create_counterparty_payload(
        user,
        comment="Smoke test (smoke_onec_urls)",
        source="website",
    )
    payload["external_id"] = f"site-smoke-{suffix}"
    return payload


def _sample_create_order_payload() -> dict[str, Any]:
    return {
        "external_order_id": f"WEB-SMOKE-{uuid.uuid4().hex[:8].upper()}",
        "order_date": "2026-02-02T10:45:00",
        "customer_id": "НФ-000580",
        "price_type": "retail",
        "warehouse_id": "MAIN",
        "items": [
            {
                "product_id": "НФ-00001137",
                "name": "Бумага A4",
                "quantity": 2,
                "price": 350.00,
                "amount": 700.00,
            }
        ],
        "total_amount": 700.00,
        "currency": "KGS",
        "delivery_required": True,
        "comment": "Заказ с сайта (smoke_onec_urls)",
        "source": "website",
    }


def _run_get(client: OneCClient, spec: OneCEndpointSpec) -> None:
    handlers: dict[str, Callable[[], Any]] = {
        PATH_COUNTERPARTY_LIST: client.fetch_counterparty_list,
        PATH_CATEGORY_LIST: client.fetch_category_list,
        PATH_CATEGORY_PRODUCT_LIST: client.fetch_category_product_list,
        PATH_PRODUCT_LIST: client.fetch_product_list,
    }
    handler = handlers.get(spec.path)
    if handler is None:
        client._request_raw("GET", spec.path)
        return
    handler()


def _run_post(client: OneCClient, spec: OneCEndpointSpec) -> None:
    if spec.path == PATH_CREATE_COUNTERPARTY:
        client.create_counterparty(_sample_create_counterparty_payload())
        return
    if spec.path == PATH_CREATE_ORDER:
        client.post_order(_sample_create_order_payload())
        return
    raise ValueError(f"Unknown POST path: {spec.path}")


def run_onec_smoke_test(
    *,
    include_mutating: bool = False,
    client: OneCClient | None = None,
) -> OneCSmokeReport:
    """Проверяет все GET-эндпоинты 1С; POST — по флагу include_mutating."""
    onec = client or OneCClient()
    base = (onec.base_url or "").rstrip("/")
    if not base:
        raise OneCAPIError("ONEC_API_BASE_URL is not configured", status_code=None)

    specs: list[OneCEndpointSpec] = list(ONEC_SMOKE_GET_ENDPOINTS)
    if include_mutating:
        specs.extend(ONEC_SMOKE_POST_ENDPOINTS)

    report = OneCSmokeReport(base_url=base)
    for spec in specs:
        url = f"{base}{spec.path}"
        start = time.perf_counter()
        try:
            if spec.method == "GET":
                _run_get(onec, spec)
            else:
                _run_post(onec, spec)
        except OneCAPIError as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            report.results.append(
                OneCSmokeResult(
                    path=spec.path,
                    method=spec.method,
                    label=spec.label,
                    url=url,
                    ok=False,
                    status_code=exc.status_code,
                    duration_ms=duration_ms,
                    detail=str(exc),
                )
            )
            continue

        duration_ms = int((time.perf_counter() - start) * 1000)
        report.results.append(
            OneCSmokeResult(
                path=spec.path,
                method=spec.method,
                label=spec.label,
                url=url,
                ok=True,
                status_code=200,
                duration_ms=duration_ms,
            )
        )

    return report


def assert_sync_paths_covered_by_smoke() -> None:
    """Sync GET-пути должны входить в smoke GET-набор."""
    smoke_paths = {s.path for s in ONEC_SMOKE_GET_ENDPOINTS}
    missing = set(ONEC_SYNC_CATALOG_GET_PATHS) - smoke_paths
    if missing:
        raise AssertionError(f"ONEC sync paths not covered by smoke GET: {sorted(missing)}")
