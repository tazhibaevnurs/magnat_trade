"""Показать JSON-тело заказа для POST …/orders/createOrder (без отправки в 1С)."""

from __future__ import annotations

import json
import uuid

from django.core.management.base import BaseCommand, CommandError

from integrations.models import OneCInteractionLog
from orders.models import Order
from orders.services.order_export import OrderExportService


class Command(BaseCommand):
    help = (
        "Показывает payload для 1С (createOrder) по заказу сайта: "
        "количества в БД, JSON для отправки и последний лог HTTP-запроса."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "order_id",
            nargs="?",
            help="UUID заказа (можно первые 8 символов, если он уникален)",
        )
        parser.add_argument(
            "--last-log",
            action="store_true",
            help="Показать последний лог createOrder из OneCInteractionLog",
        )

    def handle(self, *args, **options):
        if options["last_log"]:
            self._print_last_log()
            return

        raw = (options.get("order_id") or "").strip()
        if not raw:
            raise CommandError("Укажите order_id или --last-log")

        order = self._resolve_order(raw)
        payload = OrderExportService.build_payload(order)

        self.stdout.write(self.style.MIGRATE_HEADING(f"Заказ {order.id}"))
        self.stdout.write(f"Создан: {order.created_at:%d.%m.%Y %H:%M}")
        self.stdout.write(f"Клиент 1С (customer_id): {payload['customer_id']}")
        self.stdout.write(f"Позиций в БД: {order.items.count()}")
        self.stdout.write("")
        self.stdout.write("Количества в БД (первые 20 строк):")
        for item in order.items.all()[:20]:
            self.stdout.write(
                f"  • {item.product_id} | qty={item.quantity} | price={item.price} | {item.name_snapshot[:60]}"
            )
        if order.items.count() > 20:
            self.stdout.write(f"  … ещё {order.items.count() - 20} позиций")
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("JSON для POST …/orders/createOrder"))
        self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
        self.stdout.write("")
        self._print_matching_log(order.id)

    def _resolve_order(self, raw: str) -> Order:
        try:
            return Order.objects.prefetch_related("items").get(pk=uuid.UUID(raw))
        except ValueError:
            pass
        except Order.DoesNotExist as err:
            raise CommandError(f"Заказ не найден: {raw}") from err

        needle = raw.lower().replace("-", "")
        matches = [
            o
            for o in Order.objects.prefetch_related("items").order_by("-created_at")[:500]
            if str(o.id).replace("-", "").lower().startswith(needle)
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            ids = ", ".join(str(o.id) for o in matches[:5])
            raise CommandError(f"Найдено несколько заказов по префиксу {raw}: {ids}")
        raise CommandError(f"Заказ не найден: {raw}")

    def _print_matching_log(self, order_id: uuid.UUID) -> None:
        token = str(order_id)
        logs = (
            OneCInteractionLog.objects.filter(
                endpoint__icontains="createOrder",
                payload_summary__icontains=token,
            )
            .order_by("-created_at")[:1]
        )
        if not logs:
            logs = (
                OneCInteractionLog.objects.filter(endpoint__icontains="createOrder")
                .order_by("-created_at")[:1]
            )
        if not logs:
            self.stdout.write(self.style.WARNING("Логов createOrder в БД пока нет."))
            return
        log = logs[0]
        self.stdout.write(self.style.MIGRATE_HEADING("Последний лог HTTP → 1С (createOrder)"))
        self.stdout.write(f"Дата: {log.created_at:%d.%m.%Y %H:%M:%S}")
        self.stdout.write(f"HTTP: {log.status_code} | success={log.success}")
        if log.error_message:
            self.stdout.write(f"Ошибка: {log.error_message[:500]}")
        self.stdout.write("payload_summary (фрагмент):")
        self.stdout.write(log.payload_summary[:4000])

    def _print_last_log(self) -> None:
        log = (
            OneCInteractionLog.objects.filter(endpoint__icontains="createOrder")
            .order_by("-created_at")
            .first()
        )
        if not log:
            raise CommandError("Логов createOrder не найдено.")
        self.stdout.write(self.style.MIGRATE_HEADING("Последний createOrder в логах 1С"))
        self.stdout.write(f"Дата: {log.created_at:%d.%m.%Y %H:%M:%S}")
        self.stdout.write(f"URL: {log.endpoint}")
        self.stdout.write(f"HTTP: {log.status_code} | success={log.success}")
        if log.error_message:
            self.stdout.write(f"Ошибка: {log.error_message}")
        self.stdout.write(log.payload_summary)
