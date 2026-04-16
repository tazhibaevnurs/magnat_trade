"""Создание заказа и инициализация оплаты (для фронтенда)."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import F
from rest_framework import serializers, status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from integrations.payment.service import PaymentService
from orders.models import Order, OrderItem
from products.models import Product


def _onec_export_enabled() -> bool:
    return bool(getattr(settings, "ONEC_API_BASE_URL", "").strip())


class CheckoutConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Conflict"


class OrderItemInSerializer(serializers.Serializer):
    product_id = serializers.CharField(max_length=64)
    quantity = serializers.IntegerField(min_value=1)


class CheckoutCreateSerializer(serializers.Serializer):
    items = OrderItemInSerializer(many=True)
    price_type = serializers.ChoiceField(choices=["retail", "wholesale"], default="retail")
    currency = serializers.CharField(default="KGS", max_length=8)
    warehouse_id = serializers.CharField(required=False, allow_blank=True, default="")
    comment = serializers.CharField(required=False, allow_blank=True, default="")


class CheckoutOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = CheckoutCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        user = request.user

        if _onec_export_enabled() and not getattr(user, "external_id", None):
            return Response(
                {
                    "detail": (
                        "Контрагент 1С не привязан к профилю. "
                        "Дождитесь синхронизации клиентов или обратитесь в поддержку."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            total = Decimal("0.00")
            lines: list[tuple[str, int, Decimal, str]] = []
            for row in data["items"]:
                pid = row["product_id"]
                qty = row["quantity"]
                try:
                    p = Product.objects.select_for_update().get(id=pid, is_active=True)
                except Product.DoesNotExist as err:
                    raise ValidationError({"detail": f"Product {pid} not found"}) from err
                if p.stock < qty:
                    label = (p.sku or "").strip() or str(p.pk)
                    raise CheckoutConflict(
                        detail=f"Insufficient stock for {label}",
                    )
                price = p.retail_price if data["price_type"] == "retail" else p.wholesale_price
                line_total = price * qty
                total += line_total
                lines.append((pid, qty, price, p.name))

            warehouse = (data.get("warehouse_id") or "").strip() or getattr(
                settings, "DEFAULT_WAREHOUSE_ID", "MAIN"
            )
            order = Order.objects.create(
                user=user,
                total_amount=total,
                status="pending",
                payment_status="pending",
                delivery_status="pending",
                currency=data["currency"],
                price_type=data["price_type"],
                warehouse_id=warehouse,
                comment=data.get("comment") or "",
            )
            for pid, qty, price, name in lines:
                OrderItem.objects.create(
                    order=order,
                    product_id=pid,
                    quantity=qty,
                    price=price,
                    name_snapshot=name,
                )
            for pid, qty, _, _ in lines:
                updated = Product.objects.filter(pk=pid, stock__gte=qty).update(
                    stock=F("stock") - qty
                )
                if updated != 1:
                    raise CheckoutConflict(
                        detail=f"Не удалось зарезервировать остаток для товара {pid}",
                    )

        pay = PaymentService().create_payment(
            order_id=order.id,
            amount=order.total_amount,
            currency=order.currency,
        )
        order.payment_provider = pay.get("provider", "")
        order.payment_external_id = pay.get("payment_id", "")
        order.payment_url = pay.get("payment_url", "")
        order.save(update_fields=["payment_provider", "payment_external_id", "payment_url", "updated_at"])

        if _onec_export_enabled():
            from integrations.tasks import export_order_to_onec

            export_order_to_onec.delay(str(order.id))

        return Response(
            {
                "order_id": str(order.id),
                "total_amount": str(order.total_amount),
                "payment_url": order.payment_url,
                "payment_id": order.payment_external_id,
            },
            status=status.HTTP_201_CREATED,
        )
