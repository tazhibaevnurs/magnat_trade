# Модель WishlistItem — избранное пользователя (каталог 1С или демо-товар)

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0005_user_active_session_key"),
        ("products", "0006_gallery_and_sku"),
        ("shop", "0006_new_arrival_item"),
    ]

    operations = [
        migrations.CreateModel(
            name="WishlistItem",
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "catalog_product",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="wishlist_entries",
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
                        related_name="wishlist_entries",
                        to="shop.product",
                        verbose_name="Демо-товар витрины",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="wishlist_items",
                        to="users.user",
                    ),
                ),
            ],
            options={
                "verbose_name": "Избранное",
                "verbose_name_plural": "Избранное",
                "ordering": ("-created_at",),
            },
        ),
        migrations.AddConstraint(
            model_name="wishlistitem",
            constraint=models.CheckConstraint(
                condition=(
                    Q(catalog_product__isnull=False, shop_product__isnull=True)
                    | Q(catalog_product__isnull=True, shop_product__isnull=False)
                ),
                name="wishlistitem_catalog_xor_shop_product",
            ),
        ),
        migrations.AddConstraint(
            model_name="wishlistitem",
            constraint=models.UniqueConstraint(
                condition=Q(catalog_product__isnull=False),
                fields=("user", "catalog_product"),
                name="uniq_wishlist_user_catalog_product",
            ),
        ),
        migrations.AddConstraint(
            model_name="wishlistitem",
            constraint=models.UniqueConstraint(
                condition=Q(shop_product__isnull=False),
                fields=("user", "shop_product"),
                name="uniq_wishlist_user_shop_product",
            ),
        ),
    ]
