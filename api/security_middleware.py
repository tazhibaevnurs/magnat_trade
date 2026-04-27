import json
import logging
from time import time

from django.core.cache import cache

logger = logging.getLogger("security")


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("X-Content-Type-Options", "nosniff")
        response.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        # Conservative CSP for server-rendered app with same-origin scripts/styles.
        response.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "img-src 'self' data: https:; "
            "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com; "
            "font-src 'self' https://cdnjs.cloudflare.com https://fonts.gstatic.com; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self';",
        )
        return response


class SecurityAuditMiddleware:
    """Structured security logs + simple anomaly counters."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = time()
        response = self.get_response(request)
        elapsed_ms = int((time() - started) * 1000)
        ip = (request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or request.META.get("REMOTE_ADDR", "unknown"))
        path = request.path
        status_code = int(getattr(response, "status_code", 0) or 0)

        if path.startswith("/api/") and status_code >= 400:
            logger.warning(
                json.dumps(
                    {
                        "event": "api_error",
                        "ip": ip,
                        "path": path,
                        "method": request.method,
                        "status_code": status_code,
                        "elapsed_ms": elapsed_ms,
                        "user_id": getattr(getattr(request, "user", None), "id", None),
                    },
                    ensure_ascii=False,
                )
            )

        if status_code in (401, 403):
            key = f"sec:auth-denied:{ip}"
            denied_count = cache.get(key, 0) + 1
            cache.set(key, denied_count, timeout=300)
            if denied_count >= 20:
                logger.warning(
                    json.dumps(
                        {
                            "event": "suspicious_auth_pattern",
                            "ip": ip,
                            "window_seconds": 300,
                            "denied_count": denied_count,
                        },
                        ensure_ascii=False,
                    )
                )
        req_key = f"sec:req-count:{ip}"
        req_count = cache.get(req_key, 0) + 1
        cache.set(req_key, req_count, timeout=60)
        if req_count >= 300:
            logger.warning(
                json.dumps(
                    {
                        "event": "suspicious_request_spike",
                        "ip": ip,
                        "window_seconds": 60,
                        "request_count": req_count,
                    },
                    ensure_ascii=False,
                )
            )

        if status_code >= 500:
            err_key = f"sec:server-errors:{ip}"
            err_count = cache.get(err_key, 0) + 1
            cache.set(err_key, err_count, timeout=300)
            if err_count >= 10:
                logger.warning(
                    json.dumps(
                        {
                            "event": "server_error_spike",
                            "ip": ip,
                            "window_seconds": 300,
                            "error_count": err_count,
                        },
                        ensure_ascii=False,
                    )
                )
        return response
