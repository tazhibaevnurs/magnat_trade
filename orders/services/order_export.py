"""Формирование payload заказа для 1С и обработка ответа."""

from __future__ import annotations

import logging
from typing import Any
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from integrations.clients.onec import OneCClient
from orders.models import Order

logger = logging.getLogger(__name__)


class OrderExportService:
    @staticmethod
    def build_payload(order: Order) -> dict[str, Any]:
        from orders.constants import is_demo_line_product_id

        for line in order.items.all():
            if is_demo_line_product_id(line.product_id):
                raise ValueError("Заказ с демо-позициями не выгружается в 1С.")

        user = order.user
        if not user or not user.external_id:
            raise ValueError("User has no external_id from 1С; sync customer first.")

        items: list[dict[str, Any]] = []
        for line in order.items.all():
            items.append(
                {
                    "product_id": str(line.product_id),
                    "name": line.name_snapshot or "",
                    "quantity": line.quantity,
                    "price": float(line.price),
                    "amount": float(line.price * line.quantity),
                }
            )

        local_tz = ZoneInfo(getattr(settings, "ORDER_EXPORT_TZ", "Asia/Bishkek"))
        order_date = timezone.localtime(order.created_at, local_tz).strftime("%Y-%m-%dT%H:%M:%S")

        return {
            "external_order_id": str(order.id),
            "order_date": order_date,
            "customer_id": str(user.external_id),
            "price_type": order.price_type,
            "warehouse_id": order.warehouse_id or getattr(settings, "DEFAULT_WAREHOUSE_ID", "MAIN"),
            "items": items,
            "total_amount": float(order.total_amount),
            "currency": order.currency,
            "delivery_required": True,
            "comment": order.comment or "Заказ с сайта",
            "source": "website",
        }

    @staticmethod
    def export_to_onec(order_id: str, request_id: str | None = None) -> dict[str, Any]:
        from orders.models import Order
        import uuid

        oid = uuid.UUID(str(order_id))
        order = Order.objects.select_related("user").prefetch_related("items").get(id=oid)
        payload = OrderExportService.build_payload(order)
        client = OneCClient()
        data = client.post_order(payload, request_id=request_id)
        ext = data.get("id") or data.get("order_id")
        if ext:
            order.external_id = str(ext)
            order.status = data.get("status", order.status)
            order.save(update_fields=["external_id", "status", "updated_at"])
        return data
