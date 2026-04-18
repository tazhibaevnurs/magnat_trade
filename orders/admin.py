from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product_id", "name_snapshot", "quantity", "price")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "total_amount",
        "shipping_fee",
        "status",
        "payment_status",
        "price_type",
        "created_at",
    )
    list_filter = ("status", "payment_status", "price_type", "created_at")
    search_fields = ("id", "external_id", "delivery_email", "comment", "user__email")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [OrderItemInline]
    fieldsets = (
        (None, {"fields": ("id", "user", "external_id")}),
        ("Суммы", {"fields": ("total_amount", "shipping_fee", "currency", "price_type")}),
        ("Доставка", {"fields": ("delivery_full_name", "delivery_email", "delivery_address")}),
        ("Статусы", {"fields": ("status", "payment_status", "delivery_status")}),
        ("Оплата", {"fields": ("payment_url", "payment_provider", "payment_external_id")}),
        ("Прочее", {"fields": ("warehouse_id", "comment", "export_task_id", "last_export_error")}),
        ("Даты", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "product_id", "name_snapshot", "quantity", "price")
    search_fields = ("product_id", "name_snapshot", "order__id")
