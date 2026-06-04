"""Smoke-тест всех URL HTTP-сервиса 1С (GET + опционально POST)."""

from __future__ import annotations

import sys

from django.conf import settings
from django.core.management.base import BaseCommand

from integrations.clients.onec import OneCAPIError
from integrations.services.onec_smoke_test import run_onec_smoke_test


class Command(BaseCommand):
    help = (
        "Проверяет все URL 1С из integrations.clients.onec: "
        "GET counterparties/counterpartyList, categories/categoryList, "
        "categories_products/categoryProductList, products/productList; "
        "с --include-post также POST create_counterparty и createOrder."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--include-post",
            action="store_true",
            help="Дополнительно POST create_counterparty и createOrder (создаёт данные в 1С)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только вывести список URL без HTTP-запросов",
        )

    def handle(self, *args, **options):
        base = (getattr(settings, "ONEC_API_BASE_URL", "") or "").rstrip("/")
        if not base and not options["dry_run"]:
            self.stderr.write(self.style.ERROR("Задайте ONEC_API_BASE_URL в .env"))
            sys.exit(1)

        from integrations.services.onec_smoke_test import ONEC_SMOKE_GET_ENDPOINTS, ONEC_SMOKE_POST_ENDPOINTS

        specs = list(ONEC_SMOKE_GET_ENDPOINTS)
        if options["include_post"]:
            specs.extend(ONEC_SMOKE_POST_ENDPOINTS)

        if options["dry_run"]:
            for spec in specs:
                url = f"{base or '(ONEC_API_BASE_URL)'}{spec.path}"
                self.stdout.write(f"{spec.method} {url}  # {spec.label}")
            return

        try:
            report = run_onec_smoke_test(include_mutating=options["include_post"])
        except OneCAPIError as exc:
            self.stderr.write(self.style.ERROR(str(exc)))
            sys.exit(1)

        for row in report.results:
            status = self.style.SUCCESS("OK") if row.ok else self.style.ERROR("FAIL")
            line = f"{status} {row.method} {row.url}"
            if row.duration_ms is not None:
                line += f" ({row.duration_ms} ms)"
            if row.detail:
                line += f" — {row.detail}"
            self.stdout.write(line)

        if not report.all_ok:
            self.stderr.write(self.style.ERROR(f"Не прошло: {len(report.failed)} URL"))
            sys.exit(1)

        self.stdout.write(self.style.SUCCESS(f"Все URL OK ({len(report.results)} проверок), база: {report.base_url}"))
