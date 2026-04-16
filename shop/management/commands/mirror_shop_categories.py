"""Обновить shop.Category из products.Category (после sync_onec / импорта из 1С)."""

from django.core.management.base import BaseCommand

from shop.services.category_mirror import mirror_products_categories_to_shop


class Command(BaseCommand):
    help = "Скопировать категории из интеграции 1С (products) в витрину shop для меню и фильтров"

    def handle(self, *args, **options):
        r = mirror_products_categories_to_shop()
        self.stdout.write(self.style.SUCCESS(str(r)))
