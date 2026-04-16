from __future__ import annotations

import uuid
from typing import Any

from rest_framework import serializers


class CategorySyncItemSerializer(serializers.Serializer):
    id = serializers.CharField(max_length=64)
    name = serializers.CharField(max_length=500)
    parent_id = serializers.CharField(max_length=64, required=False, allow_null=True, allow_blank=True)
    is_active = serializers.BooleanField(required=False, default=True)


class ProductSyncItemSerializer(serializers.Serializer):
    id = serializers.CharField(max_length=64)
    sku = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    name = serializers.CharField(max_length=500)
    category_id = serializers.CharField(max_length=64)
    prices = serializers.DictField(required=False, child=serializers.FloatField())
    retail_price = serializers.DecimalField(max_digits=14, decimal_places=2, required=False)
    wholesale_price = serializers.DecimalField(max_digits=14, decimal_places=2, required=False)
    stock = serializers.IntegerField(min_value=0, default=0)
    unit = serializers.CharField(max_length=32, required=False, default="pcs")
    is_active = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        prices = attrs.get("prices") or {}
        if prices:
            attrs.setdefault("retail_price", prices.get("retail"))
            attrs.setdefault("wholesale_price", prices.get("wholesale"))
        if attrs.get("retail_price") is None or attrs.get("wholesale_price") is None:
            raise serializers.ValidationError("Укажите prices.retail/wholesale или retail_price/wholesale_price.")
        return attrs


class CustomerSyncItemSerializer(serializers.Serializer):
    external_id = serializers.CharField(max_length=64, required=False, allow_blank=True)
    id = serializers.CharField(max_length=64, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True)
    price_type = serializers.ChoiceField(choices=["retail", "wholesale"], required=False, default="retail")
    user_type = serializers.ChoiceField(choices=["retail", "wholesale"], required=False)
    entity_type = serializers.ChoiceField(
        choices=["individual", "legal_entity"],
        required=False,
        default="individual",
    )
    is_active = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs: dict) -> dict:
        if not attrs.get("external_id") and not attrs.get("id"):
            raise serializers.ValidationError("Укажите external_id или id (код из 1С).")
        if attrs.get("user_type") and not attrs.get("price_type"):
            attrs["price_type"] = attrs["user_type"]
        email = (attrs.get("email") or "").strip()
        if not email:
            ext = str(attrs.get("external_id") or attrs.get("id")).strip()
            attrs["email"] = f"onec-{ext}@imported.local"
        return attrs


class OrderStatusSerializer(serializers.Serializer):
    entity = serializers.CharField(required=False, default="order")
    id = serializers.CharField()
    status = serializers.CharField(required=False, allow_blank=True)
    payment_status = serializers.CharField(required=False, allow_blank=True)
    delivery_status = serializers.CharField(required=False, allow_blank=True)


class OrderExportSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()


class PaymentWebhookSerializer(serializers.Serializer):
    order_id = serializers.UUIDField(required=False)
    payment_id = serializers.CharField(required=False)
    status = serializers.CharField(required=False)
    event = serializers.CharField(required=False)


class SyncListWrapper(serializers.Serializer):
    """Обёртка для списка items (опционально)."""

    items = serializers.ListField(child=serializers.DictField(), required=False)
