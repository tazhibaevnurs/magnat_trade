"""Тонкие view для интеграций; бизнес-логика в services."""

from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from api.authentication import IntegrationAPIAuthentication
from api.idempotency import run_idempotent
from api.permissions import IsIntegrationCaller
from api.serializers import (
    CategorySyncItemSerializer,
    CustomerSyncItemSerializer,
    OrderExportSerializer,
    OrderStatusSerializer,
    PaymentWebhookSerializer,
    ProductSyncItemSerializer,
)
from api.throttling import IntegrationRateThrottle, WebhookRateThrottle
from integrations.clients.onec import OneCAPIError, OneCClient
from integrations.payment.service import verify_webhook_signature
from integrations.tasks import export_order_to_onec
from orders.models import Order
from orders.services import OrderStatusService
from products.services import CategorySyncService, ProductSyncService
from users.services import CustomerSyncService

logger = logging.getLogger(__name__)


def _run_idempotent(request, fn):
    return run_idempotent(request, fn)


class ProductSyncView(APIView):
    authentication_classes = [IntegrationAPIAuthentication]
    permission_classes = [IsIntegrationCaller]
    throttle_classes = [IntegrationRateThrottle]

    def post(self, request):
        def handle():
            raw_list = request.data
            if isinstance(raw_list, dict) and "items" in raw_list:
                raw_list = raw_list["items"]
            if not isinstance(raw_list, list):
                return Response({"detail": "Expected a JSON array of products"}, status=status.HTTP_400_BAD_REQUEST)
            ser = ProductSyncItemSerializer(data=raw_list, many=True)
            ser.is_valid(raise_exception=True)
            result = ProductSyncService.sync_batch(ser.validated_data)
            return Response(result, status=status.HTTP_200_OK)

        return _run_idempotent(request, handle)


class CategorySyncView(APIView):
    authentication_classes = [IntegrationAPIAuthentication]
    permission_classes = [IsIntegrationCaller]
    throttle_classes = [IntegrationRateThrottle]

    def post(self, request):
        def handle():
            raw_list = request.data
            if isinstance(raw_list, dict) and "items" in raw_list:
                raw_list = raw_list["items"]
            if not isinstance(raw_list, list):
                return Response({"detail": "Expected a JSON array of categories"}, status=status.HTTP_400_BAD_REQUEST)
            ser = CategorySyncItemSerializer(data=raw_list, many=True)
            ser.is_valid(raise_exception=True)
            result = CategorySyncService.sync_batch(ser.validated_data)
            return Response(result, status=status.HTTP_200_OK)

        return _run_idempotent(request, handle)


class CustomerSyncView(APIView):
    authentication_classes = [IntegrationAPIAuthentication]
    permission_classes = [IsIntegrationCaller]
    throttle_classes = [IntegrationRateThrottle]

    def post(self, request):
        def handle():
            raw_list = request.data
            if isinstance(raw_list, dict) and "items" in raw_list:
                raw_list = raw_list["items"]
            if not isinstance(raw_list, list):
                return Response({"detail": "Expected a JSON array of customers"}, status=status.HTTP_400_BAD_REQUEST)
            ser = CustomerSyncItemSerializer(data=raw_list, many=True)
            ser.is_valid(raise_exception=True)
            result = CustomerSyncService.sync_batch(ser.validated_data)
            return Response(result, status=status.HTTP_200_OK)

        return _run_idempotent(request, handle)


class CustomerPullFromOneCView(APIView):
    """
    Запрос GET …/counterparties/counterpartyList к 1С и сохранение контрагентов в БД (users.User).

    Аутентификация как у остальных интеграций: X-API-Key или Basic (INTEGRATION_*).
    Тело запроса не обязательно.

    Пример::

        curl -sS -X POST http://127.0.0.1:8000/api/v1/customers/pull-from-onec/ \\
          -H \"X-API-Key: $INTEGRATION_API_KEY\"
    """

    authentication_classes = [IntegrationAPIAuthentication]
    permission_classes = [IsIntegrationCaller]
    throttle_classes = [IntegrationRateThrottle]

    def post(self, request):
        try:
            client = OneCClient()
            items = client.fetch_counterparty_list()
        except OneCAPIError as exc:
            return Response(
                {"success": False, "detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        result = CustomerSyncService.sync_batch(items)
        return Response({"success": True, **result}, status=status.HTTP_200_OK)


class FullOneCSyncView(APIView):
    """
    Полная синхронизация с 1С: GET ``categoryProductList``, ``productList``, ``counterpartyList`` (опционально)
    и обновление БД — то же, что ``python manage.py sync_onec`` и Celery-задача ``sync_all_from_onec``.

    Query: ``?skip_customers=1`` — не запрашивать контрагентов.

    Пример::

        curl -sS -X POST 'http://127.0.0.1:8000/api/v1/onec/sync-full/' \\
          -H \"X-API-Key: $INTEGRATION_API_KEY\"
    """

    authentication_classes = [IntegrationAPIAuthentication]
    permission_classes = [IsIntegrationCaller]
    throttle_classes = [IntegrationRateThrottle]

    def post(self, request):
        from integrations.services.onec_full_sync import run_full_onec_sync

        skip = request.query_params.get("skip_customers", "").lower() in ("1", "true", "yes")
        try:
            result = run_full_onec_sync(skip_customers=skip)
        except OneCAPIError as exc:
            return Response(
                {"success": False, "detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        if result.get("skipped"):
            return Response(
                {"success": False, **result},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({"success": True, **result}, status=status.HTTP_200_OK)


class OrderExportView(APIView):
    authentication_classes = [IntegrationAPIAuthentication]
    permission_classes = [IsIntegrationCaller]
    throttle_classes = [IntegrationRateThrottle]

    def post(self, request):
        def handle():
            ser = OrderExportSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            oid = ser.validated_data["order_id"]
            task = export_order_to_onec.delay(str(oid), request_id=request.headers.get("X-Request-ID"))
            order = Order.objects.filter(id=oid).first()
            if order:
                order.export_task_id = task.id
                order.save(update_fields=["export_task_id", "updated_at"])
            return Response(
                {"task_id": task.id, "order_id": str(oid), "status": "queued"},
                status=status.HTTP_202_ACCEPTED,
            )

        return _run_idempotent(request, handle)


class OrderStatusView(APIView):
    authentication_classes = [IntegrationAPIAuthentication]
    permission_classes = [IsIntegrationCaller]
    throttle_classes = [IntegrationRateThrottle]

    def post(self, request):
        def handle():
            ser = OrderStatusSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            result = OrderStatusService.apply_update(ser.validated_data)
            code = status.HTTP_200_OK if result.get("ok") else status.HTTP_404_NOT_FOUND
            return Response(result, status=code)

        return _run_idempotent(request, handle)


class PaymentWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [WebhookRateThrottle]

    def post(self, request):
        raw = request.body
        sig = request.headers.get("X-Signature") or request.META.get("HTTP_X_SIGNATURE")
        if not verify_webhook_signature(raw, sig):
            return Response({"detail": "invalid signature"}, status=status.HTTP_401_UNAUTHORIZED)

        import json

        try:
            payload = json.loads(raw.decode("utf-8")) if raw else {}
        except json.JSONDecodeError:
            return Response({"detail": "invalid json"}, status=status.HTTP_400_BAD_REQUEST)

        ser = PaymentWebhookSerializer(data=payload)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        order_id = data.get("order_id")
        st = (data.get("status") or data.get("event") or "").lower()
        if order_id and ("paid" in st or st == "payment.succeeded"):
            order = Order.objects.filter(id=order_id).first()
            if order:
                order.payment_status = "paid"
                order.save(update_fields=["payment_status", "updated_at"])
        return Response({"ok": True}, status=status.HTTP_200_OK)
