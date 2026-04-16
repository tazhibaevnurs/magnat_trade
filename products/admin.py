from django.contrib import admin
from django.utils.html import format_html

from .models import Category, Product, ProductImage


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ("image", "sort_order")
    ordering = ("sort_order", "id")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "parent", "is_active", "updated_at")
    search_fields = ("name", "id")
    list_filter = ("is_active",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "image_thumb", "sku", "name", "category", "retail_price", "stock", "is_active")
    list_display_links = ("id", "name")
    search_fields = ("name", "sku", "id")
    list_filter = ("is_active", "category")
    readonly_fields = ("id", "updated_at", "gallery_preview")
    inlines = (ProductImageInline,)
    fieldsets = (
        (
            None,
            {
                "fields": ("id", "sku", "name", "category"),
                "description": "Артикул (SKU) можно оставить пустым.",
            },
        ),
        (
            "Цены и склад",
            {
                "fields": ("retail_price", "wholesale_price", "stock", "unit", "is_active"),
            },
        ),
        (
            "Галерея на сайте",
            {
                "fields": ("gallery_preview",),
                "description": "Добавьте одно или несколько фото в блоке ниже — порядок задаётся полем «Порядок».",
            },
        ),
        (
            "Служебное",
            {
                "fields": ("updated_at",),
            },
        ),
    )

    @admin.display(description="Фото")
    def image_thumb(self, obj: Product) -> str:
        img = obj.images.order_by("sort_order", "id").first()
        if img:
            return format_html(
                '<img src="{}" width="40" height="40" style="object-fit:cover;border-radius:4px" alt="" />',
                img.image.url,
            )
        return "—"

    @admin.display(description="Предпросмотр галереи")
    def gallery_preview(self, obj: Product) -> str:
        imgs = list(obj.images.order_by("sort_order", "id")[:6])
        if not imgs:
            return format_html(
                '<span class="help">Фото не добавлены — на сайте будет заглушка.</span>'
            )
        parts = [
            format_html(
                '<img src="{}" style="max-height:100px;max-width:120px;object-fit:contain;border-radius:8px;border:1px solid #e2e8f0;margin:4px" alt="" />',
                im.image.url,
            )
            for im in imgs
        ]
        return format_html("".join(parts))
