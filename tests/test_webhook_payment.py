"""Webhook оплаты и unit-тесты подписи."""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from django.test import override_settings
from django.urls import reverse


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


@pytest.mark.django_db
class TestPaymentWebhook:
    def test_rejects_invalid_signature(self, api_client):
        url = reverse("api-payments-webhook")
        body = {"order_id": "00000000-0000-4000-8000-000000000099", "status": "paid"}
        r = api_client.post(
            url,
            json.dumps(body),
            content_type="application/json",
            HTTP_X_SIGNATURE="deadbeef",
        )
        assert r.status_code == 401

    def test_marks_order_paid(
        self, api_client, order_with_items, settings
    ):
        secret = settings.PAYMENT_WEBHOOK_SECRET
        url = reverse("api-payments-webhook")
        payload = {"order_id": str(order_with_items.id), "status": "paid"}
        raw = json.dumps(payload).encode("utf-8")
        sig = _sign(raw, secret)
        r = api_client.post(
            url,
            raw,
            content_type="application/json",
            HTTP_X_SIGNATURE=sig,
        )
        assert r.status_code == 200
        order_with_items.refresh_from_db()
        assert order_with_items.payment_status == "paid"


@pytest.mark.django_db
class TestPaymentWebhookSerializer:
    """order_id в webhook — UUID."""

    def test_requires_valid_uuid(self, api_client, settings):
        secret = settings.PAYMENT_WEBHOOK_SECRET
        url = reverse("api-payments-webhook")
        payload = {"order_id": "not-a-uuid", "status": "paid"}
        raw = json.dumps(payload).encode("utf-8")
        sig = _sign(raw, secret)
        r = api_client.post(
            url,
            raw,
            content_type="application/json",
            HTTP_X_SIGNATURE=sig,
        )
        assert r.status_code == 400


def test_verify_webhook_signature_accepts_valid():
    from integrations.payment.service import verify_webhook_signature

    with override_settings(PAYMENT_WEBHOOK_SECRET="s3cr3t"):
        body = b'{"a":1}'
        sig = hmac.new(b"s3cr3t", body, hashlib.sha256).hexdigest()
        assert verify_webhook_signature(body, sig) is True


def test_verify_webhook_signature_rejects_wrong():
    from integrations.payment.service import verify_webhook_signature

    with override_settings(PAYMENT_WEBHOOK_SECRET="s3cr3t"):
        assert verify_webhook_signature(b"{}", "wrong") is False
