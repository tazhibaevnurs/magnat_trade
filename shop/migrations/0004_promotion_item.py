# Модель PromotionItem — явный список товаров для страницы «Акции»

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0006_gallery_and_sku"),
        ("shop", "0003_inventorytransaction_catalog_order"),
    ]

    operations = [
        migrations.CreateModel(
            name="PromotionItem",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "sort_order",
                    models.PositiveSmallIntegerField(
                        db_index=True,
                        default=0,
                        help_text="Меньше — выше в списке (если сортировка на сайте позволяет)",
                        verbose_name="Порядок",
                    ),
                ),
                ("is_active", models.BooleanField(default=True, verbose_name="На сайте")),
                (
                    "catalog_product",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="promotion_entries",
                        to="products.product",
                        verbose_name="Товар каталога (1С)",
                    ),
                ),
                (
                    "shop_product",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="promotion_entries",
                        to="shop.product",
                        verbose_name="Демо-товар витрины",
                    ),
                ),
            ],
            options={
                "verbose_name": "Товар в акции",
                "verbose_name_plural": "Акции: товары",
                "ordering": ("sort_order", "id"),
            },
        ),
        migrations.AddConstraint(
            model_name="promotionitem",
            constraint=models.CheckConstraint(
                condition=(
                    Q(catalog_product__isnull=False, shop_product__isnull=True)
                    | Q(catalog_product__isnull=True, shop_product__isnull=False)
                ),
                name="shop_promotionitem_catalog_xor_shop_product",
            ),
        ),
        migrations.AddConstraint(
            model_name="promotionitem",
            constraint=models.UniqueConstraint(
                condition=Q(catalog_product__isnull=False),
                fields=("catalog_product",),
                name="shop_promotionitem_uniq_catalog_product",
            ),
        ),
        migrations.AddConstraint(
            model_name="promotionitem",
            constraint=models.UniqueConstraint(
                condition=Q(shop_product__isnull=False),
                fields=("shop_product",),
                name="shop_promotionitem_uniq_shop_product",
            ),
        ),
    ]
