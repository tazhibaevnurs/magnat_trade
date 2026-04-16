"""Заглушка доставки для разработки и тестов."""

from __future__ import annotations

from decimal import Decimal
import uuid

from .base import (
    DeliveryAddress,
    DeliveryProvider,
    DeliveryQuote,
    ShipmentResult,
    TrackingInfo,
)


class MockDeliveryProvider(DeliveryProvider):
    code = "mock"

    def quote(
        self,
        *,
        weight_kg: Decimal | None,
        address: DeliveryAddress,
        order_total: Decimal,
    ) -> DeliveryQuote:
        base = Decimal("150.00")
        return DeliveryQuote(
            price=base,
            currency="KGS",
            provider_code=self.code,
            eta_days=3,
            raw={"mock": True},
        )

    def create_shipment(
        self,
        *,
        order_external_id: str,
        address: DeliveryAddress,
        price: Decimal,
        comment: str = "",
    ) -> ShipmentResult:
        return ShipmentResult(
            delivery_id=f"MOCK-{uuid.uuid4().hex[:12].upper()}",
            status="created",
            raw={"order_id": order_external_id},
        )

    def track(self, delivery_id: str) -> TrackingInfo:
        return TrackingInfo(status="in_transit", details={"id": delivery_id})


def get_delivery_provider() -> DeliveryProvider:
    from django.conf import settings

    code = getattr(settings, "DELIVERY_PROVIDER", "mock")
    if code == "mock":
        return MockDeliveryProvider()
    return MockDeliveryProvider()
