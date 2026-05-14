"""Выгрузка всего каталога товаров (products.Product) в Excel."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from openpyxl import Workbook

from products.models import Product


def _excel_row(p: Product) -> list:
    cat = p.category
    cat_id = str(cat.pk)
    cat_name = cat.name
    upd = p.updated_at
    if upd is not None and timezone.is_aware(upd):
        upd = timezone.localtime(upd).replace(tzinfo=None)
    elif upd is not None:
        upd = upd.replace(tzinfo=None)
    return [
        str(p.pk),
        (p.sku or "").strip(),
        p.name,
        cat_id,
        cat_name,
        float(p.retail_price),
        float(p.wholesale_price),
        int(p.stock),
        (p.unit or "").strip(),
        bool(p.is_active),
        upd,
    ]


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
        qs = Product.objects.select_related("category").order_by("category__name", "name")
        if options["active_only"]:
            qs = qs.filter(is_active=True)

        out_arg = options.get("output")
        if out_arg:
            out_path = Path(out_arg).expanduser().resolve()
        else:
            ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            out_path = (Path(settings.BASE_DIR) / "exports" / f"catalog_products_{ts}.xlsx").resolve()

        out_path.parent.mkdir(parents=True, exist_ok=True)

        wb = Workbook(write_only=True)
        ws = wb.create_sheet(title="Товары", index=0)
        hdr = (
            "Код 1С (id)",
            "Артикул",
            "Название",
            "Код категории",
            "Категория",
            "Розничная цена",
            "Оптовая цена",
            "Остаток",
            "Ед. изм.",
            "Активен",
            "Обновлён в БД",
        )
        ws.append(list(hdr))

        n = 0
        total = qs.count()
        for p in qs.iterator(chunk_size=500):
            ws.append(_excel_row(p))
            n += 1
            if n % 2000 == 0:
                self.stdout.write(f"... строк: {n} / {total}")

        wb.save(out_path)
        self.stdout.write(self.style.SUCCESS(f"Готово: {n} товаров -> {out_path}"))
