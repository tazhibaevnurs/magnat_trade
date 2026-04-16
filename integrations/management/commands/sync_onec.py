"""Односторонняя загрузка справочников из 1С (GET categoryProductList, productList, counterpartyList)."""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand

from integrations.clients.onec import OneCAPIError
from integrations.services.onec_full_sync import run_full_onec_sync


class Command(BaseCommand):
    help = "Загрузить из 1С категории, товары и контрагентов в локальную БД Django"

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-customers",
            action="store_true",
            help="Не синхронизировать контрагентов (только категории и товары)",
        )

    def handle(self, *args, **options):
        if not (settings.ONEC_API_BASE_URL or "").strip():
            self.stderr.write(self.style.ERROR("Задайте ONEC_API_BASE_URL в окружении."))
            return

        try:
            result = run_full_onec_sync(skip_customers=options["skip_customers"])
        except OneCAPIError as exc:
            self.stderr.write(self.style.ERROR(f"Ошибка API 1С: {exc}"))
            raise

        if result.get("skipped"):
            self.stderr.write(self.style.WARNING(str(result)))
            return

        self.stdout.write(self.style.SUCCESS(f"URL 1С: {result.get('onec_urls_requested', [])}"))
        for key in ("categories", "mirror_shop_categories", "products", "customers"):
            if key in result:
                self.stdout.write(self.style.SUCCESS(f"{key}: {result[key]}"))
