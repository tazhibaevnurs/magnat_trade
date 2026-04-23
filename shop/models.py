"""Модели витрины: демо-каталог, корзина (общая), профиль, заказы только для shop.Product.

Заказы каталога 1С — orders.Order (таблица orders_order), создаются из корзины с products.Product.
См. docs/DATA_MODEL_DOMAINS.md
"""

import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils.text import slugify


def product_image_upload_path(instance, filename):
    ext = filename.split(".")[-1]
    name = getattr(instance.product, "slug", None) or str(instance.product_id)
    return os.path.join("products", f"{name}_{instance.pk or 'new'}.{ext}")


def profile_picture_upload_path(instance, filename):
    ext = filename.split(".")[-1]
    return os.path.join("profiles", f"user_{instance.user_id}_profile.{ext}")


class Category(models.Model):
    """Иерархия категорий (родитель + slug)."""

    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children",
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, db_index=True)

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or "category"
            s = base
            n = 1
            while Category.objects.filter(slug=s).exclude(pk=self.pk).exists():
                s = f"{base}-{n}"
                n += 1
            self.slug = s
        super().save(*args, **kwargs)


class UserProfile(models.Model):
    CURRENCY_CHOICES = [
        ("KGS", "Кыргызский сом (с)"),
        ("USD", "US Dollar ($)"),
        ("RUB", "Российский рубль (₽)"),
    ]

    PAYMENT_METHOD_CHOICES = [
        ("COD", "Наличными при получении"),
        ("CARD", "Банковская карта"),
        ("ELWALLET", "Электронный кошелёк"),
        ("BANK", "Банковский перевод"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    house_address = models.CharField(max_length=255, blank=True)
    contact_number = models.CharField(max_length=20, blank=True, default="")
    profile_picture = models.ImageField(
        upload_to=profile_picture_upload_path,
        blank=True,
        null=True,
        help_text="Upload a profile picture",
    )
    preferred_currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default="KGS",
        help_text="Preferred currency for pricing",
    )
    preferred_payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default="COD",
        help_text="Preferred payment method",
    )

    class Meta:
        verbose_name = "Профиль пользователя"
        verbose_name_plural = "Профили пользователей"

    def __str__(self) -> str:
        return f"{self.user.email}'s profile"

    def get_user_full_name(self):
        return f"{self.user.first_name} {self.user.last_name}".strip()

    @property
    def profile_picture_url(self):
        if self.profile_picture and hasattr(self.profile_picture, "url"):
            return self.profile_picture.url
        return None


class Address(models.Model):
    ADDRESS_TYPE_CHOICES = [
        ("home", "Дом"),
        ("work", "Работа"),
        ("other", "Другое"),
    ]

    COUNTRY_CHOICES = [
        ("Kyrgyzstan", "Кыргызстан"),
        ("Philippines", "Philippines"),
        ("United States", "United States"),
        ("Canada", "Canada"),
        ("United Kingdom", "United Kingdom"),
        ("Australia", "Australia"),
        ("Japan", "Japan"),
        ("South Korea", "South Korea"),
        ("Singapore", "Singapore"),
        ("Malaysia", "Malaysia"),
        ("Thailand", "Thailand"),
        ("Indonesia", "Indonesia"),
        ("Vietnam", "Vietnam"),
        ("India", "India"),
        ("China", "China"),
        ("Hong Kong", "Hong Kong"),
        ("Taiwan", "Taiwan"),
        ("Germany", "Germany"),
        ("France", "France"),
        ("Italy", "Italy"),
        ("Spain", "Spain"),
        ("Netherlands", "Netherlands"),
        ("Belgium", "Belgium"),
        ("Switzerland", "Switzerland"),
        ("Austria", "Austria"),
        ("Sweden", "Sweden"),
        ("Norway", "Norway"),
        ("Denmark", "Denmark"),
        ("Finland", "Finland"),
        ("Brazil", "Brazil"),
        ("Mexico", "Mexico"),
        ("Argentina", "Argentina"),
        ("Chile", "Chile"),
        ("Colombia", "Colombia"),
        ("Peru", "Peru"),
        ("New Zealand", "New Zealand"),
        ("South Africa", "South Africa"),
        ("United Arab Emirates", "United Arab Emirates"),
        ("Saudi Arabia", "Saudi Arabia"),
        ("Israel", "Israel"),
        ("Turkey", "Turkey"),
        ("Russia", "Russia"),
        ("Other", "Other"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="addresses",
    )
    label = models.CharField(max_length=100, help_text="Address label (e.g., Home, Work)")
    address_type = models.CharField(max_length=20, choices=ADDRESS_TYPE_CHOICES, default="home")
    street_address = models.CharField(max_length=255, help_text="Street address")
    city = models.CharField(max_length=100)
    state_province = models.CharField(max_length=100, help_text="State/Province")
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100, choices=COUNTRY_CHOICES, default="Kyrgyzstan")
    is_default = models.BooleanField(default=False, help_text="Set as default address")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Адрес"
        verbose_name_plural = "Адреса"
        ordering = ["-is_default", "-created_at"]

    def __str__(self) -> str:
        return f"{self.user.email} - {self.label}"

    def save(self, *args, **kwargs):
        if self.is_default:
            Address.objects.filter(user=self.user, is_default=True).update(is_default=False)
        super().save(*args, **kwargs)

    @property
    def full_address(self) -> str:
        return f"{self.street_address}, {self.city}, {self.state_province} {self.postal_code}, {self.country}"


class Product(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(
        max_length=250,
        unique=True,
        blank=True,
        help_text="URL-friendly version of the product name (auto-generated)",
    )
    description = models.TextField()
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Акционная цена; если задана и ниже price — показывается она",
    )
    stock = models.PositiveIntegerField(default=0, help_text="Количество на складе")
    weight = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Weight in grams (g)",
    )
    dimensions = models.CharField(
        max_length=100,
        blank=True,
        help_text="Product dimensions (e.g., '21cm x 14.8cm')",
    )
    is_active = models.BooleanField(default=True, help_text="Whether this product is available for purchase")
    is_featured = models.BooleanField(default=False, help_text="Mark as featured product (shown on homepage)")
    is_bestseller = models.BooleanField(default=False, help_text="Mark as bestseller")
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} — {self.current_price} сом"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("pdp", kwargs={"slug": self.slug})

    @property
    def current_price(self):
        from decimal import Decimal

        if self.discount_price is not None and self.discount_price < self.price:
            return self.discount_price
        return self.price

    @property
    def is_catalog_product(self) -> bool:
        return False

    @property
    def measure_line(self) -> str:
        """Фасовка для карточки товара (в духе av.ru: «1 шт», «500 г»)."""
        if self.weight is not None:
            try:
                w = float(self.weight)
                if w >= 1000:
                    val = w / 1000
                    s = f"{val:.2f}".rstrip("0").rstrip(".")
                    return f"{s} кг"
                return f"{int(w)} г"
            except (TypeError, ValueError):
                pass
        return "1 шт"

    @property
    def image_url(self):
        first = self.images.order_by("sort_order", "id").first()
        if first and first.image:
            return first.image.url
        return "/static/shop/images/placeholder-product.svg"

    @property
    def is_in_stock(self):
        return self.stock > 0 and self.is_active

    @property
    def stock_status(self):
        if not self.is_active:
            return "Снято с продажи"
        if self.stock == 0:
            return "Нет в наличии"
        if self.stock <= 5:
            return "Мало на складе"
        return "В наличии"

    @property
    def is_new_arrival(self):
        from datetime import timedelta

        from django.utils import timezone

        return self.created_at >= timezone.now() - timedelta(days=30)


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to=product_image_upload_path)
    alt = models.CharField(max_length=255, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "Изображение товара"
        verbose_name_plural = "Изображения товаров"
        ordering = ["sort_order", "id"]

    def __str__(self) -> str:
        return f"{self.product.name} #{self.pk}"


class Cart(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="carts",
    )
    session_key = models.CharField(max_length=40, blank=True, null=True, help_text="Session key for anonymous carts")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Корзина"
        verbose_name_plural = "Корзины"
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        owner = self.user.email if self.user else f"session:{self.session_key}"
        return f"Cart {self.pk} ({owner})"

    def item_count(self):
        return sum(item.quantity for item in self.items.all())

    def total_price(self):
        from decimal import Decimal

        total = Decimal("0.00")
        for item in self.items.all():
            total += item.total_price()
        return total


class CartItem(models.Model):
    """Позиция: либо демо-товар shop.Product, либо номенклатура 1С (products.Product)."""

    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="cart_items",
    )
    catalog_product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="shop_cart_items",
    )
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    special_instructions = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Позиция в корзине"
        verbose_name_plural = "Позиции в корзине"
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(product__isnull=False, catalog_product__isnull=True)
                    | Q(product__isnull=True, catalog_product__isnull=False)
                ),
                name="cartitem_shop_xor_catalog",
            ),
            models.UniqueConstraint(
                fields=("cart", "product"),
                name="uniq_cartitem_shop_product_pair",
            ),
            models.UniqueConstraint(
                fields=("cart", "catalog_product"),
                name="uniq_cartitem_catalog_product_pair",
            ),
        ]

    def __str__(self) -> str:
        name = (
            self.catalog_product.name
            if self.catalog_product_id
            else (self.product.name if self.product_id else "?")
        )
        return f"{self.quantity} × {name} (cart {self.cart.pk})"

    def save(self, *args, **kwargs):
        if self.catalog_product_id and not self.price:
            self.price = self.catalog_product.retail_price
        elif self.product_id and not self.price:
            self.price = self.product.current_price
        super().save(*args, **kwargs)

    def total_price(self):
        return self.price * self.quantity

    @property
    def is_catalog_line(self) -> bool:
        return self.catalog_product_id is not None


class WishlistItem(models.Model):
    """Избранное пользователя: одна строка — либо товар 1С, либо демо-товар витрины."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wishlist_items",
    )
    catalog_product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="wishlist_entries",
        verbose_name="Товар каталога (1С)",
    )
    shop_product = models.ForeignKey(
        "Product",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="wishlist_entries",
        verbose_name="Демо-товар витрины",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Избранное"
        verbose_name_plural = "Избранное"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(catalog_product__isnull=False, shop_product__isnull=True)
                    | Q(catalog_product__isnull=True, shop_product__isnull=False)
                ),
                name="wishlistitem_catalog_xor_shop_product",
            ),
            models.UniqueConstraint(
                fields=("user", "catalog_product"),
                name="uniq_wishlist_user_catalog_product_pair",
            ),
            models.UniqueConstraint(
                fields=("user", "shop_product"),
                name="uniq_wishlist_user_shop_product_pair",
            ),
        ]

    def __str__(self) -> str:
        if self.catalog_product_id:
            return f"{self.user} → {self.catalog_product_id}"
        if self.shop_product_id:
            return f"{self.user} → {self.shop_product}"
        return f"{self.user} → ?"

    def clean(self):
        super().clean()
        has_catalog = self.catalog_product_id is not None
        has_shop = self.shop_product_id is not None
        if has_catalog == has_shop:
            raise ValidationError(
                "Укажите ровно один товар: либо номенклатуру 1С, либо демо-товар витрины."
            )


class Order(models.Model):
    STATUS_CHOICES = [
        ("pending", "В обработке"),
        ("out_for_delivery", "Передан в доставку"),
        ("delivered", "Доставлен"),
        ("returned", "Возврат"),
        ("refunded", "Возврат средств"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    full_name = models.CharField(max_length=100)
    email = models.EmailField()
    address = models.CharField(max_length=255)
    payment_method = models.CharField(max_length=20, default="COD")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    placed_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"

    def __str__(self) -> str:
        return f"Order #{self.pk} by {self.full_name} ({self.payment_method})"

    def get_price_without_shipping(self):
        return self.total_amount - self.shipping_fee


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    class Meta:
        verbose_name = "Позиция заказа"
        verbose_name_plural = "Позиции заказа"

    def __str__(self) -> str:
        pn = self.product.name if self.product else "Deleted Product"
        return f"{self.quantity} × {pn} (Order #{self.order.pk})"

    def get_subtotal(self):
        return self.price * self.quantity


class Feedback(models.Model):
    STATUS_CHOICES = [
        ("unread", "Не прочитано"),
        ("read", "Прочитано"),
        ("archived", "В архиве"),
    ]

    CATEGORY_CHOICES = [
        ("general", "Общее"),
        ("bug", "Ошибка"),
        ("feature", "Предложение"),
        ("complaint", "Жалоба"),
        ("compliment", "Благодарность"),
        ("other", "Другое"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="feedbacks",
    )
    name = models.CharField(max_length=100, help_text="Customer name")
    email = models.EmailField(help_text="Contact email")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="general")
    subject = models.CharField(max_length=200, help_text="Feedback subject")
    message = models.TextField(help_text="Feedback message")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="unread")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    admin_notes = models.TextField(blank=True, help_text="Internal notes for admins")

    class Meta:
        verbose_name = "Обратная связь"
        verbose_name_plural = "Обратная связь"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} - {self.subject} ({self.created_at.strftime('%Y-%m-%d')})"

    def mark_as_read(self):
        self.status = "read"
        self.save()

    def mark_as_archived(self):
        self.status = "archived"
        self.save()


class InventoryTransaction(models.Model):
    TRANSACTION_TYPES = [
        ("sale", "Продажа"),
        ("restock", "Пополнение"),
        ("adjustment", "Ручная корректировка"),
        ("return", "Возврат"),
        ("damaged", "Бой/потеря"),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="inventory_transactions")
    catalog_order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="demo_inventory_transactions",
        help_text="Единый заказ (orders_order), если продажа с демо-витрины.",
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_transactions",
        help_text="Устаревший заказ shop_order (старые записи).",
    )
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    quantity_change = models.IntegerField(help_text="Positive for additions, negative for deductions")
    stock_before = models.PositiveIntegerField(help_text="Stock quantity before this transaction")
    stock_after = models.PositiveIntegerField(help_text="Stock quantity after this transaction")
    notes = models.TextField(blank=True, help_text="Additional notes about this transaction")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_transactions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Операция по складу"
        verbose_name_plural = "Операции по складу"

    def __str__(self) -> str:
        return f"{self.transaction_type.upper()}: {self.product.name} ({self.quantity_change:+d}) - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class PromotionItem(models.Model):
    """Явный список товаров для страницы «Акции»: номенклатура 1С или демо-товар витрины (ровно один)."""

    catalog_product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="promotion_entries",
        verbose_name="Товар каталога (1С)",
    )
    shop_product = models.ForeignKey(
        "Product",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="promotion_entries",
        verbose_name="Демо-товар витрины",
    )
    sort_order = models.PositiveSmallIntegerField(
        default=0,
        db_index=True,
        verbose_name="Порядок",
        help_text="Меньше — выше в списке (если сортировка на сайте позволяет)",
    )
    is_active = models.BooleanField(default=True, verbose_name="На сайте")

    class Meta:
        verbose_name = "Товар в акции"
        verbose_name_plural = "Акции: товары"
        ordering = ["sort_order", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(catalog_product__isnull=False, shop_product__isnull=True)
                    | Q(catalog_product__isnull=True, shop_product__isnull=False)
                ),
                name="shop_promotionitem_catalog_xor_shop_product",
            ),
            models.UniqueConstraint(
                fields=["catalog_product"],
                name="shop_promotionitem_uniq_catalog_product_key",
            ),
            models.UniqueConstraint(
                fields=["shop_product"],
                name="shop_promotionitem_uniq_shop_product_key",
            ),
        ]

    def __str__(self) -> str:
        if self.catalog_product_id:
            return f"Акция (1С): {self.catalog_product}"
        if self.shop_product_id:
            return f"Акция (витрина): {self.shop_product}"
        return "Акция (не задан товар)"

    def clean(self):
        super().clean()
        has_catalog = self.catalog_product_id is not None
        has_shop = self.shop_product_id is not None
        if has_catalog == has_shop:
            raise ValidationError(
                "Укажите ровно один товар: либо номенклатуру 1С, либо демо-товар витрины."
            )


class NewArrivalItem(models.Model):
    """Явный список товаров для страницы «Новинки» (номенклатура 1С или демо-товар — ровно один)."""

    catalog_product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="new_arrival_entries",
        verbose_name="Товар каталога (1С)",
    )
    shop_product = models.ForeignKey(
        "Product",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="new_arrival_entries",
        verbose_name="Демо-товар витрины",
    )
    sort_order = models.PositiveSmallIntegerField(
        default=0,
        db_index=True,
        verbose_name="Порядок",
        help_text="Меньше — выше в списке (если сортировка на сайте позволяет)",
    )
    is_active = models.BooleanField(default=True, verbose_name="На сайте")

    class Meta:
        verbose_name = "Товар в новинках"
        verbose_name_plural = "Новинки: товары"
        ordering = ["sort_order", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(catalog_product__isnull=False, shop_product__isnull=True)
                    | Q(catalog_product__isnull=True, shop_product__isnull=False)
                ),
                name="shop_newarrivalitem_catalog_xor_shop_product",
            ),
            models.UniqueConstraint(
                fields=["catalog_product"],
                name="shop_newarrivalitem_uniq_catalog_product_key",
            ),
            models.UniqueConstraint(
                fields=["shop_product"],
                name="shop_newarrivalitem_uniq_shop_product_key",
            ),
        ]

    def __str__(self) -> str:
        if self.catalog_product_id:
            return f"Новинка (1С): {self.catalog_product}"
        if self.shop_product_id:
            return f"Новинка (витрина): {self.shop_product}"
        return "Новинка (не задан товар)"

    def clean(self):
        super().clean()
        has_catalog = self.catalog_product_id is not None
        has_shop = self.shop_product_id is not None
        if has_catalog == has_shop:
            raise ValidationError(
                "Укажите ровно один товар: либо номенклатуру 1С, либо демо-товар витрины."
            )
