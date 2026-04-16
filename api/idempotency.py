"""Идемпотентность POST через заголовок Idempotency-Key (Redis cache)."""

from __future__ import annotations

import hashlib
from typing import Callable

from django.core.cache import cache
from django.utils.encoding import force_bytes
from rest_framework.response import Response


def run_idempotent(
    request,
    build_response: Callable[[], Response],
    *,
    ttl: int = 86400,
) -> Response:
    """
    При наличии Idempotency-Key кэширует (data, status_code) ответа.
    Повторный запрос с тем же ключом и телом возвращает тот же ответ.
    """
    key_header = request.headers.get("Idempotency-Key") or request.META.get("HTTP_IDEMPOTENCY_KEY")
    body_hash = hashlib.sha256(force_bytes(request.body or b"")).hexdigest()[:32]
    path = request.path

    if not key_header:
        return build_response()

    cache_key = f"idemp:{path}:{key_header}:{body_hash}"
    cached = cache.get(cache_key)
    if cached is not None:
        data, status_code = cached
        resp = Response(data, status=status_code)
        resp["X-Idempotent-Replayed"] = "true"
        return resp

    response = build_response()
    try:
        data = response.data
        serializable = dict(data) if hasattr(data, "keys") else {"result": data}
        cache.set(cache_key, (serializable, response.status_code), ttl)
    except Exception:  # noqa: BLE001
        pass
    return response
