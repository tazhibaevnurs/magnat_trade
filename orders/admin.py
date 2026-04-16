from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    raw_id_fields = ()


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "external_id", "user", "total_amount", "status", "payment_status", "delivery_status", "created_at")
    list_filter = ("status", "payment_status", "delivery_status")
    search_fields = ("id", "external_id", "user__email")
    inlines = [OrderItemInline]
    raw_id_fields = ("user",)
