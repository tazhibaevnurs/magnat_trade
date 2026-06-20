"""Выгрузка всего каталога товаров (products.Product) в Excel."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from products.models import Product
from products.services.catalog_excel_export import build_catalog_excel_bytes


class Command(BaseCommand):
    help = "Экспорт всех товаров каталога из БД в файл .xlsx (openpyxl)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            "-o",
            type=str,
            default=None,
            help="Путь к .xlsx (по умолчанию exports/catalog_products_ГГГГ-ММ-ДД_ЧЧ-ММ-СС.xlsx в корне проекта)",
        )
        parser.add_argument(
            "--active-only",
            action="store_true",
            help="Только активные товары (is_active=true). По умолчанию экспортируются все строки каталога.",
        )

    def handle(self, *args, **options):
        active_only = bool(options["active_only"])
        out_arg = options.get("output")
        if out_arg:
            out_path = Path(out_arg).expanduser().resolve()
        else:
            ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            out_path = (Path(settings.BASE_DIR) / "exports" / f"catalog_products_{ts}.xlsx").resolve()

        out_path.parent.mkdir(parents=True, exist_ok=True)
        data = build_catalog_excel_bytes(active_only=active_only)
        out_path.write_bytes(data)

        qs = Product.objects.all()
        if active_only:
            qs = qs.filter(is_active=True)
        n = qs.count()
        self.stdout.write(self.style.SUCCESS(f"Готово: {n} товаров -> {out_path}"))
