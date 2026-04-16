"""Проверочный POST в 1С «Создание заказа» (как в руководстве)."""

from __future__ import annotations

import json
import sys

from django.conf import settings
from django.core.management.base import BaseCommand

from integrations.clients.onec import OneCAPIError, OneCClient


class Command(BaseCommand):
    help = (
        "Отправляет тестовый JSON на ONEC_API_BASE_URL/orders/createOrder. "
        "Требуются ONEC_API_BASE_URL и Basic-авторизация в настройках."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только показать URL и пример тела, без HTTP-запроса",
        )

    def handle(self, *args, **options):
        base = (getattr(settings, "ONEC_API_BASE_URL", "") or "").rstrip("/")
        if not base and not options["dry_run"]:
            self.stderr.write(self.style.ERROR("Задайте ONEC_API_BASE_URL в .env"))
            sys.exit(1)

        payload = {
            "external_order_id": "WEB-SMOKE-CLI",
            "order_date": "2026-02-02T10:45:00",
            "customer_id": "НФ-000580",
            "price_type": "retail",
            "warehouse_id": "MAIN",
            "items": [
                {
                    "product_id": "НФ-00001137",
                    "name": "Бумага A4",
                    "quantity": 2,
                    "price": 350.00,
                    "amount": 700.00,
                }
            ],
            "total_amount": 700.00,
            "currency": "KGS",
            "delivery_required": True,
            "comment": "Заказ с сайта (smoke_onec_create_order)",
            "source": "website",
        }

        url = f"{base}/orders/createOrder" if base else "(ONEC_API_BASE_URL не задан)"
        self.stdout.write(f"POST {url}\n")
        self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))

        if options["dry_run"]:
            return

        client = OneCClient()
        try:
            data = client.post_order(payload)
        except OneCAPIError as exc:
            self.stderr.write(self.style.ERROR(str(exc)))
            if getattr(exc, "body", None) is not None:
                self.stderr.write(repr(exc.body))
            sys.exit(1)

        self.stdout.write(self.style.SUCCESS(json.dumps(data, ensure_ascii=False, indent=2)))
