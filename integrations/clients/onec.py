"""HTTP-клиент для публикации 1С HTTP-сервиса (см. «Руководство к API.docx»)."""

from __future__ import annotations

import base64
import logging
import time
import uuid
from typing import Any

import httpx
from django.conf import settings
from tenacity import retry, stop_after_attempt, wait_exponential

from integrations.models import OneCInteractionLog

logger = logging.getLogger(__name__)

from integrations.onec_constants import ONEC_DEFAULT_BASE_URL

# Пути относительно ONEC_API_BASE_URL (например …/bereke/hs)
PATH_CREATE_COUNTERPARTY = "/counterparties/create_counterparty"
PATH_COUNTERPARTY_LIST = "/counterparties/counterpartyList"
PATH_CATEGORY_LIST = "/categories/categoryList"
PATH_CATEGORY_PRODUCT_LIST = "/categories_products/categoryProductList"
PATH_PRODUCT_LIST = "/products/productList"
PATH_CREATE_ORDER = "/orders/createOrder"

# GET-запросы полной синхронизации справочников → БД (см. integrations.services.onec_full_sync)
ONEC_SYNC_CATALOG_GET_PATHS: tuple[str, ...] = (
    PATH_CATEGORY_PRODUCT_LIST,
    PATH_PRODUCT_LIST,
    PATH_COUNTERPARTY_LIST,
)


class OneCAPIError(Exception):
    def __init__(self, message: str, status_code: int | None = None, body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class OneCClient:
    def __init__(self) -> None:
        self.base_url = getattr(settings, "ONEC_API_BASE_URL", "").rstrip("/")
        self.token = getattr(settings, "ONEC_API_TOKEN", "")
        self.source = getattr(settings, "ONEC_API_SOURCE", "website")
        self.timeout = float(getattr(settings, "ONEC_API_TIMEOUT", 30))
        self.auth_type = getattr(settings, "ONEC_AUTH_TYPE", "basic").strip().lower()
        self.basic_user = (getattr(settings, "ONEC_API_BASIC_USER", "") or "").strip()
        self.basic_password = (getattr(settings, "ONEC_API_BASIC_PASSWORD", "") or "").strip()
        self.basic_auth_raw = (getattr(settings, "ONEC_API_BASIC_AUTH", "") or "").strip()
        self.verify_ssl = getattr(settings, "ONEC_VERIFY_SSL", True)
        self.send_extra_headers = getattr(settings, "ONEC_SEND_EXTRA_HEADERS", True)

    def _authorization_value(self) -> str | None:
        """
        Basic из руководства: в curl после «Basic » идёт одна base64-строка.
        Приоритет: ONEC_API_BASIC_AUTH (как в документе), иначе пара user/password.
        Так пустые/забытые USER/PASS из .env.example не перекрывают готовый токен.
        """
        if self.auth_type == "basic":
            if self.basic_auth_raw:
                return (
                    self.basic_auth_raw
                    if self.basic_auth_raw.startswith("Basic ")
                    else f"Basic {self.basic_auth_raw}"
                )
            if self.basic_user or self.basic_password:
                raw = f"{self.basic_user}:{self.basic_password}".encode("utf-8")
                return "Basic " + base64.b64encode(raw).decode("ascii")
            return None
        if self.token:
            return f"Bearer {self.token}"
        return None

    def _headers(self, request_id: str | None = None) -> dict[str, str]:
        rid = request_id or str(uuid.uuid4())
        h: dict[str, str] = {
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
        }
        if self.send_extra_headers:
            h["X-Source"] = self.source
            h["X-Request-ID"] = rid
        auth = self._authorization_value()
        if auth:
            h["Authorization"] = auth
        return h

    def _log(
        self,
        *,
        direction: str,
        endpoint: str,
        method: str,
        request_id: str,
        status_code: int | None,
        success: bool,
        payload_summary: str,
        error_message: str,
        duration_ms: int | None,
    ) -> None:
        try:
            OneCInteractionLog.objects.create(
                direction=direction,
                endpoint=endpoint,
                method=method,
                request_id=request_id,
                status_code=status_code,
                success=success,
                payload_summary=payload_summary[:8000],
                error_message=error_message[:4000],
                duration_ms=duration_ms,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to persist OneC log: %s", exc)

    def _request_raw(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> tuple[int, Any]:
        if not self.base_url:
            raise OneCAPIError("ONEC_API_BASE_URL is not configured", status_code=None)
        if self.auth_type == "basic" and not self._authorization_value():
            raise OneCAPIError(
                "Basic-авторизация не задана: в .env укажите ONEC_API_BASIC_AUTH (base64 из curl в руководстве) "
                "или пару ONEC_API_BASIC_USER / ONEC_API_BASIC_PASSWORD",
                status_code=None,
            )

        rid = request_id or str(uuid.uuid4())
        url = f"{self.base_url}{path}"
        start = time.perf_counter()
        summary = str(json_body)[:2000] if json_body else ""
        try:
            # Self-signed cert on 1C server, verification disabled when ONEC_VERIFY_SSL=false.
            with httpx.Client(timeout=self.timeout, verify=self.verify_ssl) as client:
                resp = client.request(
                    method,
                    url,
                    headers=self._headers(rid),
                    json=json_body,
                )
        except httpx.HTTPError as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            self._log(
                direction="outbound",
                endpoint=url,
                method=method,
                request_id=rid,
                status_code=None,
                success=False,
                payload_summary=summary,
                error_message=str(exc),
                duration_ms=duration_ms,
            )
            raise OneCAPIError(str(exc)) from exc

        duration_ms = int((time.perf_counter() - start) * 1000)
        try:
            data = resp.json() if resp.content else None
        except Exception:  # noqa: BLE001
            data = {"raw": resp.text[:2000]}

        ok = 200 <= resp.status_code < 300
        err_msg = ""
        if not ok:
            if isinstance(data, dict):
                err_msg = str(data.get("message") or data.get("error") or data)[:2000]
            else:
                err_msg = str(data)[:2000] if data is not None else resp.text[:500]
        self._log(
            direction="outbound",
            endpoint=url,
            method=method,
            request_id=rid,
            status_code=resp.status_code,
            success=ok,
            payload_summary=summary,
            error_message=err_msg or "",
            duration_ms=duration_ms,
        )

        if not ok:
            msg = err_msg or f"HTTP {resp.status_code}"
            if resp.status_code == 401:
                msg += (
                    " — неверные учётные данные или устарел пароль. "
                    "Проверьте ONEC_API_BASIC_AUTH в .env (без лишних кавычек и пробелов); "
                    "если заданы USER/PASS, они должны совпадать с пользователем публикации 1С."
                )
            raise OneCAPIError(
                msg,
                status_code=resp.status_code,
                body=data,
            )
        return resp.status_code, data

    @staticmethod
    def _coerce_list_payload(data: Any) -> list[dict[str, Any]]:
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        if isinstance(data, dict):
            for key in ("items", "data", "counterparties", "result", "values", "rows"):
                inner = data.get(key)
                if isinstance(inner, list):
                    return [x for x in inner if isinstance(x, dict)]
        raise OneCAPIError("Expected JSON array or object with list from counterpartyList", body=data)

    def fetch_counterparty_list(self, request_id: str | None = None) -> list[dict[str, Any]]:
        _, data = self._request_raw("GET", PATH_COUNTERPARTY_LIST, request_id=request_id)
        return self._coerce_list_payload(data)

    def fetch_category_list(self, request_id: str | None = None) -> list[dict[str, Any]]:
        _, data = self._request_raw("GET", PATH_CATEGORY_LIST, request_id=request_id)
        if not isinstance(data, list):
            raise OneCAPIError("Expected JSON array from categoryList", body=data)
        return [x for x in data if isinstance(x, dict)]

    def fetch_category_product_list(self, request_id: str | None = None) -> Any:
        """GET categories_products/categoryProductList — дерево категорий (и опционально товары в JSON)."""
        _, data = self._request_raw("GET", PATH_CATEGORY_PRODUCT_LIST, request_id=request_id)
        return data

    def fetch_product_list(self, request_id: str | None = None) -> list[dict[str, Any]]:
        _, data = self._request_raw("GET", PATH_PRODUCT_LIST, request_id=request_id)
        if not isinstance(data, list):
            raise OneCAPIError("Expected JSON array from productList", body=data)
        return [x for x in data if isinstance(x, dict)]

    def create_counterparty(self, payload: dict[str, Any], request_id: str | None = None) -> dict[str, Any]:
        _, data = self._request_raw(
            "POST",
            PATH_CREATE_COUNTERPARTY,
            json_body=payload,
            request_id=request_id,
        )
        if not isinstance(data, dict):
            raise OneCAPIError("Expected JSON object from create_counterparty", body=data)
        return data

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=1, max=10),
    )
    def post_order(self, payload: dict[str, Any], request_id: str | None = None) -> dict[str, Any]:
        _, data = self._request_raw(
            "POST",
            PATH_CREATE_ORDER,
            json_body=payload,
            request_id=request_id,
        )
        if not isinstance(data, dict):
            raise OneCAPIError("Expected JSON object from createOrder", body=data)
        return data
