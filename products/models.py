"""Номенклатура и категории синхронизации с 1С (область A).

Демо-категории и демо-товары витрины — модели shop.Category и shop.Product.
См. docs/DATA_MODEL_DOMAINS.md
"""

import os
import uuid

from django.db import models


def product_gallery_upload_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower() or ".jpg"
    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        ext = ".jpg"
    pid = str(instance.product_id or "new")
    uid = str(instance.pk) if instance.pk else uuid.uuid4().hex[:16]
    return os.path.join("products", "catalog", pid, f"{uid}{ext}")


class Category(models.Model):
    """Категория из 1С; первичный ключ — код из 1С (например НФ-000479) или N-* из дерева categoryProductList.

    Товары привязаны через ``Product.category`` (ForeignKey); отдельная M2M не используется.
    """

    id = models.CharField(
        primary_key=True,
        max_length=64,
        editable=False,
        verbose_name="Код категории",
    )
    slug = models.SlugField(
        max_length=220,
        unique=True,
        db_index=True,
        allow_unicode=True,
        help_text="ЧПУ для ссылок на сайте (генерируется из кода и названия 1С).",
    )
    name = models.CharField(max_length=500, verbose_name="Название")
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children",
    )
    is_active = models.BooleanField(default=True, db_index=True, verbose_name="Активна")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Product(models.Model):
    """Товар из 1С; первичный ключ — код номенклатуры из 1С (например НФ-00004612)."""

    id = models.CharField(primary_key=True, max_length=64, editable=False, verbose_name="Код товара")
    sku = models.CharField(max_length=120, db_index=True, blank=True, default="", verbose_name="Артикул")
    name = models.CharField(max_length=500, verbose_name="Название")
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
        verbose_name="Категория",
    )
    retail_price = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="Розничная цена")
    wholesale_price = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="Оптовая цена")
    stock = models.PositiveIntegerField(default=0, verbose_name="Остаток")
    unit = models.CharField(max_length=32, default="pcs", verbose_name="Ед. изм.")
    is_active = models.BooleanField(default=True, db_index=True, verbose_name="Активен")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["sku"]),
            models.Index(fields=["is_active", "updated_at"]),
        ]

    def __str__(self) -> str:
        if self.sku:
            return f"{self.name} ({self.sku})"
        return self.name

    @property
    def image_url(self) -> str:
        """Первое фото галереи или заглушка."""
        first = self.images.order_by("sort_order", "id").first()
        if first:
            return first.image.url
        return "/static/shop/images/placeholder-product.svg"

    @property
    def gallery_urls(self) -> list[str]:
        return [img.image.url for img in self.images.order_by("sort_order", "id")]


class ProductImage(models.Model):
    """Фото товара в галерее (несколько штук на одну номенклатуру)."""

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="images",
        verbose_name="Товар",
    )
    image = models.ImageField(upload_to=product_gallery_upload_path, verbose_name="Изображение")
    sort_order = models.PositiveSmallIntegerField(
        default=0,
        help_text="Порядок слева направо (меньше — раньше).",
        verbose_name="Порядок",
    )

    class Meta:
        verbose_name = "Фото в галерее"
        verbose_name_plural = "Галерея фото"
        ordering = ["sort_order", "id"]

    def __str__(self) -> str:
        return f"{self.product_id} #{self.pk}"
