"""Создание платежа и проверка webhook (HMAC-SHA256)."""

from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from decimal import Decimal
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)


def verify_webhook_signature(raw_body: bytes, signature_header: str | None, *, stripe_signature: str | None = None) -> bool:
    """Проверка подписи webhook: generic HMAC-SHA256 и Stripe-compatible header."""
    if stripe_signature:
        stripe_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "") or ""
        if not stripe_secret:
            return False
        try:
            parts = dict(item.split("=", 1) for item in stripe_signature.split(",") if "=" in item)
            ts = parts.get("t", "")
            v1 = parts.get("v1", "")
            signed_payload = f"{ts}.{raw_body.decode('utf-8')}".encode("utf-8")
            expected = hmac.new(stripe_secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
            return bool(v1) and hmac.compare_digest(expected, v1)
        except Exception:  # noqa: BLE001
            return False

    secret = getattr(settings, "PAYMENT_WEBHOOK_SECRET", "") or ""
    if not secret or not signature_header:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    try:
        return hmac.compare_digest(expected, signature_header.strip())
    except Exception:  # noqa: BLE001
        return False


class PaymentService:
    """Интеграция с платёжным провайдером: создание сессии оплаты."""

    def __init__(self) -> None:
        self.provider = getattr(settings, "PAYMENT_PROVIDER", "stub")
        self.base_return_url = getattr(settings, "PAYMENT_RETURN_URL", "https://example.com/payment/return")

    def create_payment(
        self,
        *,
        order_id: uuid.UUID,
        amount: Decimal,
        currency: str,
        description: str = "",
    ) -> dict[str, Any]:
        """
        Возвращает payment_url и внешний id платежа.
        В production здесь вызывается API провайдера (CloudPayments и т.д.).
        """
        external_id = f"pay_{uuid.uuid4().hex}"
        # Заглушка: фронт редиректит на этот URL; в тестах можно PATCH order через API
        payment_url = (
            f"{getattr(settings, 'PUBLIC_SITE_URL', 'http://localhost:8000').rstrip('/')}"
            f"/api/v1/payments/complete/?order_id={order_id}&token={external_id}"
        )
        return {
            "payment_id": external_id,
            "payment_url": payment_url,
            "provider": self.provider,
        }
