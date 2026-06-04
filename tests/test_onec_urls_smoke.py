"""Автотесты URL интеграции с 1С."""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

from integrations.clients.onec import (
    ONEC_SYNC_CATALOG_GET_PATHS,
    PATH_CATEGORY_LIST,
    PATH_CATEGORY_PRODUCT_LIST,
    PATH_COUNTERPARTY_LIST,
    PATH_CREATE_COUNTERPARTY,
    PATH_CREATE_ORDER,
    PATH_PRODUCT_LIST,
    OneCAPIError,
)
from integrations.onec_constants import ONEC_DEFAULT_BASE_URL
from integrations.services.onec_smoke_test import (
    ONEC_SMOKE_GET_ENDPOINTS,
    ONEC_SMOKE_POST_ENDPOINTS,
    assert_sync_paths_covered_by_smoke,
    run_onec_smoke_test,
)


@pytest.mark.parametrize(
    "path",
    [
        PATH_COUNTERPARTY_LIST,
        PATH_CATEGORY_LIST,
        PATH_CATEGORY_PRODUCT_LIST,
        PATH_PRODUCT_LIST,
        PATH_CREATE_COUNTERPARTY,
        PATH_CREATE_ORDER,
    ],
)
def test_onec_endpoint_urls_use_bereke_base(path):
    base = ONEC_DEFAULT_BASE_URL.rstrip("/")
    assert "/bereke/" in base
    assert "bereke_test" not in base
    url = f"{base}{path}"
    assert url.startswith("https://rdp.it-help.kg:4443/bereke/")


def test_sync_catalog_paths_covered_by_smoke_get():
    assert_sync_paths_covered_by_smoke()
    smoke_paths = {s.path for s in ONEC_SMOKE_GET_ENDPOINTS}
    assert set(ONEC_SYNC_CATALOG_GET_PATHS).issubset(smoke_paths)


def test_smoke_get_endpoints_count():
    assert len(ONEC_SMOKE_GET_ENDPOINTS) == 4
    assert len(ONEC_SMOKE_POST_ENDPOINTS) == 2


def test_smoke_create_counterparty_payload_includes_is_active():
    from integrations.services.onec_smoke_test import _sample_create_counterparty_payload

    payload = _sample_create_counterparty_payload()
    assert payload.get("is_active") is True
    assert payload.get("comment")
    assert payload.get("external_id", "").startswith("site-smoke-")


@pytest.mark.django_db
def test_run_onec_smoke_test_all_get_ok(settings):
    settings.ONEC_API_BASE_URL = ONEC_DEFAULT_BASE_URL
    settings.ONEC_AUTH_TYPE = "basic"
    settings.ONEC_API_BASIC_AUTH = "Basic dGVzdDp0ZXN0"

    client = MagicMock()
    client.base_url = ONEC_DEFAULT_BASE_URL
    client.fetch_counterparty_list.return_value = []
    client.fetch_category_list.return_value = []
    client.fetch_category_product_list.return_value = {}
    client.fetch_product_list.return_value = []

    report = run_onec_smoke_test(client=client)

    assert report.all_ok
    assert len(report.results) == 4
    assert client.fetch_counterparty_list.called
    assert client.fetch_category_list.called
    assert client.fetch_category_product_list.called
    assert client.fetch_product_list.called
    for row in report.results:
        assert row.url.startswith(ONEC_DEFAULT_BASE_URL)


@pytest.mark.django_db
def test_run_onec_smoke_test_records_failure(settings):
    settings.ONEC_API_BASE_URL = ONEC_DEFAULT_BASE_URL
    settings.ONEC_AUTH_TYPE = "basic"
    settings.ONEC_API_BASIC_AUTH = "Basic dGVzdDp0ZXN0"

    client = MagicMock()
    client.base_url = ONEC_DEFAULT_BASE_URL
    client.fetch_counterparty_list.side_effect = OneCAPIError("HTTP 401", status_code=401)
    client.fetch_category_list.return_value = []
    client.fetch_category_product_list.return_value = {}
    client.fetch_product_list.return_value = []

    report = run_onec_smoke_test(client=client)

    assert not report.all_ok
    assert len(report.failed) == 1
    assert report.failed[0].status_code == 401


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("ONEC_SMOKE_LIVE") != "1",
    reason="Live 1C smoke: set ONEC_SMOKE_LIVE=1 (PowerShell: $env:ONEC_SMOKE_LIVE='1') and credentials in .env",
)
@pytest.mark.django_db
def test_live_onec_smoke_get_urls(settings):
    """Реальный запрос ко всем GET URL 1С (требует .env с ONEC_API_*)."""
    base = (os.getenv("ONEC_API_BASE_URL") or ONEC_DEFAULT_BASE_URL).rstrip("/")
    settings.ONEC_API_BASE_URL = base

    report = run_onec_smoke_test(include_mutating=False)
    assert report.all_ok, [(r.url, r.detail) for r in report.failed]
