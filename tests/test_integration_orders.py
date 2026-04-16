"""Статусы заказов и выгрузка в 1С."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestOrderStatus:
    def test_updates_by_external_id(self, api_client, integration_headers, order_with_items):
        order_with_items.external_id = "ORDER-999"
        order_with_items.save(update_fields=["external_id"])

        url = reverse("api-orders-status")
        r = api_client.post(
            url,
            {
                "entity": "order",
                "id": "ORDER-999",
                "status": "shipped",
                "payment_status": "paid",
                "delivery_status": "in_transit",
            },
            format="json",
            **integration_headers,
        )
        assert r.status_code == 200
        assert r.json()["ok"] is True
        order_with_items.refresh_from_db()
        assert order_with_items.status == "shipped"
        assert order_with_items.payment_status == "paid"
        assert order_with_items.delivery_status == "in_transit"

    def test_updates_by_order_uuid_string(self, api_client, integration_headers, order_with_items):
        url = reverse("api-orders-status")
        r = api_client.post(
            url,
            {
                "id": str(order_with_items.id),
                "status": "delivered",
            },
            format="json",
            **integration_headers,
        )
        assert r.status_code == 200
        order_with_items.refresh_from_db()
        assert order_with_items.status == "delivered"

    def test_not_found(self, api_client, integration_headers):
        url = reverse("api-orders-status")
        r = api_client.post(
            url,
            {"id": "UNKNOWN-ORDER", "status": "x"},
            format="json",
            **integration_headers,
        )
        assert r.status_code == 404


@pytest.mark.django_db
class TestOrderExport:
    @patch("api.views.export_order_to_onec.delay")
    def test_queues_task_and_sets_export_task_id(
        self, mock_delay, api_client, integration_headers, order_with_items
    ):
        mock_delay.return_value = MagicMock(id="fake-celery-id")

        url = reverse("api-orders-export")
        r = api_client.post(
            url,
            {"order_id": str(order_with_items.id)},
            format="json",
            **integration_headers,
        )
        assert r.status_code == 202
        data = r.json()
        assert data["status"] == "queued"
        assert data["task_id"] == "fake-celery-id"
        mock_delay.assert_called_once()
        order_with_items.refresh_from_db()
        assert order_with_items.export_task_id == "fake-celery-id"
