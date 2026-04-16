"""Абстракция провайдера доставки (расчёт, отправление, трекинг)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class DeliveryAddress:
    country: str
    city: str
    street: str
    house: str
    flat: str = ""


@dataclass(frozen=True)
class DeliveryQuote:
    price: Decimal
    currency: str
    provider_code: str
    eta_days: int | None = None
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class ShipmentResult:
    delivery_id: str
    status: str
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class TrackingInfo:
    status: str
    details: dict[str, Any]


class DeliveryProvider(ABC):
    code: str = "abstract"

    @abstractmethod
    def quote(
        self,
        *,
        weight_kg: Decimal | None,
        address: DeliveryAddress,
        order_total: Decimal,
    ) -> DeliveryQuote:
        """Расчёт стоимости доставки."""

    @abstractmethod
    def create_shipment(
        self,
        *,
        order_external_id: str,
        address: DeliveryAddress,
        price: Decimal,
        comment: str = "",
    ) -> ShipmentResult:
        """Создание отправления у провайдера."""

    @abstractmethod
    def track(self, delivery_id: str) -> TrackingInfo:
        """Трекинг по идентификатору отправления."""
