from __future__ import annotations

import uuid

from orders.models import Order


class OrderRepository:
    @staticmethod
    def get_by_id(order_id: uuid.UUID) -> Order | None:
        return Order.objects.filter(id=order_id).first()

    @staticmethod
    def update_statuses(
        *,
        external_id: str | None = None,
        order_uuid: uuid.UUID | None = None,
        status: str | None = None,
        payment_status: str | None = None,
        delivery_status: str | None = None,
    ) -> Order | None:
        qs = Order.objects.all()
        order = None
        if external_id:
            order = qs.filter(external_id=external_id).first()
        if order is None and order_uuid:
            order = qs.filter(id=order_uuid).first()
        if order is None and external_id:
            try:
                oid = uuid.UUID(str(external_id))
                order = qs.filter(id=oid).first()
            except (ValueError, TypeError):
                order = None
        if not order:
            return None
        fields: list[str] = []
        if status is not None:
            order.status = status
            fields.append("status")
        if payment_status is not None:
            order.payment_status = payment_status
            fields.append("payment_status")
        if delivery_status is not None:
            order.delivery_status = delivery_status
            fields.append("delivery_status")
        if fields:
            fields.append("updated_at")
            order.save(update_fields=fields)
        return order
