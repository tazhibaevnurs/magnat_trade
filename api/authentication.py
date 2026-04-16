"""API Key или Basic Auth для эндпоинтов интеграции 1С."""

import base64
import secrets

from django.conf import settings
from rest_framework import authentication, exceptions


class IntegrationAPIAuthentication(authentication.BaseAuthentication):
    """
    Поддержка:
    - заголовок X-API-Key: <key>
    - Authorization: Basic base64(user:password) при INTEGRATION_BASIC_USER / INTEGRATION_BASIC_PASSWORD
    """

    keyword = b"Basic"

    def authenticate(self, request):
        api_key = request.headers.get("X-API-Key") or request.META.get("HTTP_X_API_KEY")
        expected = getattr(settings, "INTEGRATION_API_KEY", "") or ""
        if api_key and expected and secrets.compare_digest(api_key, expected):
            return (None, "integration-api-key")

        auth = request.headers.get("Authorization", "")
        if auth.startswith("Basic "):
            try:
                raw = base64.b64decode(auth[6:].strip()).decode("utf-8")
                user, _, password = raw.partition(":")
            except Exception as exc:  # noqa: BLE001
                raise exceptions.AuthenticationFailed("Invalid Basic auth") from exc
            exp_user = getattr(settings, "INTEGRATION_BASIC_USER", "") or ""
            exp_pass = getattr(settings, "INTEGRATION_BASIC_PASSWORD", "") or ""
            if exp_user and exp_pass and secrets.compare_digest(user, exp_user) and secrets.compare_digest(
                password, exp_pass
            ):
                return (None, "integration-basic")

        return None

    def authenticate_header(self, request):
        return 'Basic realm="integration"'
