from django.contrib import admin
from django.db.models import F

from .constants import demo_shop_product_pk, is_demo_line_product_id
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product_id", "name_snapshot", "quantity", "price")


def _restock_order_items(items_queryset, acting_user=None) -> None:
    """
    Возврат остатков на склад при удалении заказа/позиции из админки.
    - обычные строки: products.Product (каталог 1С)
    - DEMO:* строки: shop.Product (демо-витрина)
    """
    from products.models import Product as CatalogProduct
    from shop.models import Product as ShopProduct

    for item in items_queryset:
        qty = int(item.quantity or 0)
        if qty <= 0:
            continue
        pid = str(item.product_id)
        if is_demo_line_product_id(pid):
            shop_pk = demo_shop_product_pk(pid)
            if shop_pk is not None:
                ShopProduct.objects.filter(pk=shop_pk).update(stock=F("stock") + qty)
        else:
            CatalogProduct.objects.filter(pk=pid).update(stock=F("stock") + qty)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "user",
        "total_amount",
        "onec_sync_status",
        "delivery_method",
        "shipping_fee",
        "status",
        "payment_status",
        "price_type",
        "created_at",
    )
    list_filter = ("status", "payment_status", "price_type", "delivery_method", "created_at")
    search_fields = ("id", "external_id", "delivery_email", "comment", "user__email")
    readonly_fields = ("id", "created_at", "updated_at", "onec_sync_status")
    inlines = [OrderItemInline]
    fieldsets = (
        (None, {"fields": ("id", "user", "external_id")}),
        ("Суммы", {"fields": ("total_amount", "shipping_fee", "currency", "price_type")}),
        (
            "Доставка",
            {
                "fields": (
                    "delivery_method",
                    "delivery_full_name",
                    "delivery_email",
                    "delivery_phone",
                    "delivery_address",
                )
            },
        ),
        ("Статусы", {"fields": ("status", "payment_status", "delivery_status", "onec_sync_status")}),
        ("Оплата", {"fields": ("payment_url", "payment_provider", "payment_external_id")}),
        (
            "Прочее",
            {"fields": ("warehouse_id", "customer_comment", "comment", "export_task_id", "last_export_error")},
        ),
        ("Даты", {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(description="Синхронизация 1С")
    def onec_sync_status(self, obj: Order) -> str:
        return obj.onec_sync_state_label

    @admin.display(description="Номер заказа", ordering="id")
    def order_number(self, obj: Order) -> str:
        value = str(obj.id).upper()
        return f"#{value[:8]}"

    def delete_model(self, request, obj):
        _restock_order_items(obj.items.all(), acting_user=request.user)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        # Восстановим остатки для всех удаляемых заказов.
        for order in queryset.prefetch_related("items"):
            _restock_order_items(order.items.all(), acting_user=request.user)
        super().delete_queryset(request, queryset)


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order_number", "product_id", "name_snapshot", "quantity", "price")
    search_fields = ("product_id", "name_snapshot", "order__id")

    @admin.display(description="Номер заказа", ordering="order__id")
    def order_number(self, obj: OrderItem) -> str:
        value = str(obj.order_id).upper()
        return f"#{value[:8]}"

    def delete_model(self, request, obj):
        order_id = obj.order_id
        _restock_order_items(OrderItem.objects.filter(pk=obj.pk), acting_user=request.user)
        super().delete_model(request, obj)
        if order_id and not OrderItem.objects.filter(order_id=order_id).exists():
            Order.objects.filter(pk=order_id).delete()

    def delete_queryset(self, request, queryset):
        order_ids = list(queryset.values_list("order_id", flat=True).distinct())
        _restock_order_items(queryset, acting_user=request.user)
        super().delete_queryset(request, queryset)
        if order_ids:
            empty_order_ids = [
                oid for oid in order_ids if not OrderItem.objects.filter(order_id=oid).exists()
            ]
            if empty_order_ids:
                Order.objects.filter(pk__in=empty_order_ids).delete()
