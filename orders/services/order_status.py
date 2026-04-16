from __future__ import annotations

from typing import Any

from orders.repositories import OrderRepository


class OrderStatusService:
    @staticmethod
    def apply_update(payload: dict[str, Any]) -> dict[str, Any]:
        entity = payload.get("entity")
        if entity and entity != "order":
            return {"ok": False, "error": "unsupported entity"}

        ext_id = payload.get("id")
        status_val = payload.get("status") or None
        payment_status = payload.get("payment_status") or None
        delivery_status = payload.get("delivery_status") or None
        if status_val == "":
            status_val = None

        order = OrderRepository.update_statuses(
            external_id=str(ext_id) if ext_id else None,
            status=status_val,
            payment_status=payment_status,
            delivery_status=delivery_status,
        )
        if not order:
            return {"ok": False, "error": "order not found"}

        return {"ok": True, "order_id": str(order.id)}
