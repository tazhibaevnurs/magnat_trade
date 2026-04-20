"""Единые заказы сайта: каталог 1С, API и демо-витрина (shop.Product).

Устаревшая таблица shop_order не используется для новых заказов.
См. docs/DATA_MODEL_DOMAINS.md
"""

import uuid

from django.conf import settings
from django.db import models

from .constants import DEMO_PRODUCT_LINE_PREFIX


class Order(models.Model):
    """Заказ сайта; external_id — номер/ид из 1С после выгрузки."""
    class DeliveryMethod(models.TextChoices):
        PICKUP = "pickup", "Самовывоз"
        COURIER = "courier", "Курьерская доставка"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    external_id = models.CharField(
        max_length=120,
        null=True,
        blank=True,
        unique=True,
        db_index=True,
        help_text="ID заказа в 1С (например ORDER-000124)",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="catalog_orders",
    )
    total_amount = models.DecimalField(max_digits=14, decimal_places=2)
    shipping_fee = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Доставка (для отображения; итог в total_amount).",
    )
    delivery_method = models.CharField(
        max_length=20,
        choices=DeliveryMethod.choices,
        default=DeliveryMethod.PICKUP,
        db_index=True,
        help_text="Способ доставки клиента.",
    )
    delivery_full_name = models.CharField(max_length=120, blank=True, default="")
    delivery_email = models.EmailField(blank=True, default="")
    delivery_phone = models.CharField(max_length=32, blank=True, default="")
    delivery_address = models.TextField(blank=True, default="")

    status = models.CharField(max_length=64, default="draft", db_index=True)
    payment_status = models.CharField(max_length=64, default="pending", db_index=True)
    delivery_status = models.CharField(max_length=64, default="pending", db_index=True)

    payment_url = models.URLField(max_length=2000, blank=True, default="")
    payment_provider = models.CharField(max_length=64, blank=True, default="")
    payment_external_id = models.CharField(max_length=255, blank=True, default="")

    currency = models.CharField(max_length=8, default="KGS")
    price_type = models.CharField(max_length=20, default="retail")
    warehouse_id = models.CharField(max_length=64, blank=True, default="")
    comment = models.TextField(blank=True, default="")
    customer_comment = models.TextField(blank=True, default="")

    export_task_id = models.CharField(max_length=255, blank=True, default="")
    last_export_error = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["external_id"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"Order {self.id} ({self.external_id or '—'})"

    @property
    def goods_subtotal(self):
        from decimal import Decimal

        fee = self.shipping_fee or Decimal("0")
        return self.total_amount - fee

    @property
    def delivery_method_label(self) -> str:
        return self.get_delivery_method_display()

    @property
    def requires_onec_export(self) -> bool:
        return self.items.exclude(product_id__startswith=DEMO_PRODUCT_LINE_PREFIX).exists()

    @property
    def onec_sync_state_code(self) -> str:
        if not self.requires_onec_export:
            return "not_required"
        if self.external_id:
            return "exported"
        if self.last_export_error:
            return "error"
        return "queued"

    @property
    def onec_sync_state_label(self) -> str:
        code = self.onec_sync_state_code
        if code == "exported":
            return "В 1С отправлен"
        if code == "error":
            return "Ошибка выгрузки в 1С"
        if code == "queued":
            return "В очереди на выгрузку в 1С"
        return "Выгрузка в 1С не требуется"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product_id = models.CharField(max_length=64, db_index=True)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=14, decimal_places=2)
    name_snapshot = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="Наименование на момент заказа (для 1С)",
    )

    class Meta:
        verbose_name = "Позиция заказа"
        verbose_name_plural = "Позиции заказа"

    def __str__(self) -> str:
        return f"{self.product_id} × {self.quantity}"

    @property
    def line_total(self):
        return self.price * self.quantity
