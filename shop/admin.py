from datetime import date, timedelta

from django.contrib import admin
from django.db.models import Count, DecimalField, F, Q, Sum
from django.shortcuts import render
from django.urls import path
from django.utils.html import format_html

from .models import (
    Address,
    Cart,
    CartItem,
    Category,
    Feedback,
    InventoryTransaction,
    Order,
    OrderItem,
    Product,
    ProductImage,
)

admin.site.site_header = "Magnat Trade — Админка"
admin.site.site_title = "Magnat Trade"
admin.site.index_title = "Управление сайтом"


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "parent")
    list_filter = ("parent",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "category",
        "price",
        "discount_price",
        "stock",
        "is_featured",
        "is_bestseller",
        "stock_status_display",
        "is_active",
        "image_preview",
        "created_at",
    )
    list_filter = ("category", "is_active", "is_featured", "is_bestseller", "created_at")
    search_fields = ("name", "description", "slug")
    readonly_fields = ("slug", "created_at", "modified_at", "image_preview", "stock_status_display")
    list_per_page = 25
    list_editable = ("price", "stock", "is_active", "is_featured", "is_bestseller")
    inlines = [ProductImageInline]

    fieldsets = (
        ("Основное", {"fields": ("name", "slug", "description", "category", "price", "discount_price")}),
        ("Остатки и наличие", {"fields": ("stock", "is_active", "stock_status_display")}),
        ("Отображение на сайте", {"fields": ("is_featured", "is_bestseller")}),
        ("Характеристики", {"fields": ("weight", "dimensions"), "classes": ("collapse",)}),
        ("Превью", {"fields": ("image_preview",)}),
        ("Даты", {"fields": ("created_at", "modified_at"), "classes": ("collapse",)}),
    )

    @admin.display(description="Превью")
    def image_preview(self, obj):
        url = obj.image_url
        if url and not url.endswith("placeholder-product.svg"):
            return format_html(
                '<img src="{}" width="100" height="100" style="object-fit: cover; border-radius: 4px;" />',
                url,
            )
        return format_html(
            '<div style="width:100px;height:100px;background:#f0f0f0;border-radius:4px;display:flex;align-items:center;justify-content:center;color:#666;">Нет фото</div>'
        )

    @admin.display(description="Наличие")
    def stock_status_display(self, obj):
        status = obj.stock_status
        colors = {
            "В наличии": "green",
            "Мало на складе": "orange",
            "Нет в наличии": "red",
            "Снято с продажи": "gray",
        }
        color = colors.get(status, "black")
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, status)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path("sales-analytics/", self.admin_site.admin_view(self.sales_analytics_view), name="sales-analytics"),
        ]
        return custom_urls + urls

    def sales_analytics_view(self, request):
        total_orders = Order.objects.count()
        total_revenue = Order.objects.aggregate(total=Sum("total_amount"))["total"] or 0
        completed_orders = Order.objects.filter(status="delivered").count()
        pending_orders = Order.objects.filter(status="pending").count()

        top_products = (
            OrderItem.objects.values("product__name")
            .annotate(total_sold=Sum("quantity"), revenue=Sum("price"))
            .order_by("-total_sold")[:10]
        )

        context = dict(
            self.admin_site.each_context(request),
            total_orders=total_orders,
            total_revenue=total_revenue,
            completed_orders=completed_orders,
            pending_orders=pending_orders,
            top_products=top_products,
            bottom_products=[],
            monthly_sales=[],
            month_options=[],
            selected_month=None,
        )
        return render(request, "admin/sales_analytics.html", context)


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "session_key", "is_active", "created_at", "updated_at")
    search_fields = ("user__email", "session_key")
    readonly_fields = ("created_at", "updated_at")


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("id", "cart", "product", "catalog_product", "quantity", "price", "created_at")
    search_fields = ("product__name", "catalog_product__name", "catalog_product__sku")
    readonly_fields = ("created_at", "updated_at")


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "product", "quantity", "price", "total_price")
    list_filter = ("order__status", "product")
    search_fields = ("order__id", "product__name")
    readonly_fields = ("total_price",)


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "category", "subject", "status", "created_at")
    list_filter = ("status", "category", "created_at")
    search_fields = ("name", "email", "subject", "message")
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("Клиент", {"fields": ("user", "name", "email")}),
        ("Обращение", {"fields": ("category", "subject", "message", "status")}),
        ("Для админа", {"fields": ("admin_notes", "created_at", "updated_at")}),
    )

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ("user", "name", "email", "category", "subject", "message")
        return self.readonly_fields

    actions = ["mark_as_read", "mark_as_archived"]

    def mark_as_read(self, request, queryset):
        queryset.update(status="read")
        self.message_user(request, f"Отмечено как прочитанное: {queryset.count()}.")

    mark_as_read.short_description = "Отметить как прочитанное"

    def mark_as_archived(self, request, queryset):
        queryset.update(status="archived")
        self.message_user(request, f"В архив: {queryset.count()}.")

    mark_as_archived.short_description = "В архив"


@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "product",
        "transaction_type",
        "quantity_change_display",
        "stock_before",
        "stock_after",
        "order_link",
        "created_by",
    )
    list_filter = ("transaction_type", "created_at", "product__category")
    search_fields = ("product__name", "order__id", "notes", "created_by__email")
    readonly_fields = ("created_at", "stock_before", "stock_after")

    @admin.display(description="Изменение")
    def quantity_change_display(self, obj):
        color = "green" if obj.quantity_change > 0 else "red"
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:+d}</span>',
            color,
            obj.quantity_change,
        )

    @admin.display(description="Заказ")
    def order_link(self, obj):
        if obj.order:
            from django.urls import reverse

            url = reverse("admin:shop_order_change", args=[obj.order.id])
            return format_html('<a href="{}">Заказ №{}</a>', url, obj.order.id)
        return "-"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "inventory-dashboard/",
                self.admin_site.admin_view(self.inventory_dashboard),
                name="inventory-dashboard",
            ),
        ]
        return custom_urls + urls

    def inventory_dashboard(self, request):
        from datetime import datetime

        low_stock_products = Product.objects.filter(stock__lte=5, is_active=True).order_by("stock")
        out_of_stock = Product.objects.filter(stock=0, is_active=True).count()
        thirty_days_ago = datetime.now() - timedelta(days=30)
        recent_transactions = (
            InventoryTransaction.objects.filter(created_at__gte=thirty_days_ago)
            .select_related("product", "order", "created_by")
            .order_by("-created_at")[:50]
        )
        total_inventory_value = Product.objects.aggregate(
            total=Sum(F("stock") * F("price"), output_field=DecimalField())
        )["total"] or 0

        context = dict(
            self.admin_site.each_context(request),
            low_stock_products=low_stock_products,
            out_of_stock_count=out_of_stock,
            recent_transactions=recent_transactions,
            stock_movement=[],
            top_selling=[],
            total_inventory_value=total_inventory_value,
            products_needing_restock=Product.objects.filter(Q(stock__lte=10) & Q(is_active=True)).count(),
            title="Склад и остатки",
        )
        return render(request, "admin/inventory_dashboard.html", context)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name", "email", "total_amount", "shipping_fee", "status", "placed_at", "user")
    search_fields = ("full_name", "email", "address", "user__email")
    list_filter = ("status", "payment_method", "placed_at")
    list_editable = ("status",)

    def get_readonly_fields(self, request, obj=None):
        # id нет в форме создания; дата и склад — только у сохранённого заказа
        if obj is None:
            return ()
        return ("id", "placed_at", "inventory_impact_display")

    def get_fieldsets(self, request, obj=None):
        order_fields = ("user", "full_name", "email", "address")
        if obj is not None:
            order_fields = ("id", "user", "full_name", "email", "address")
        sections = [
            ("Заказ", {"fields": order_fields}),
            ("Оплата", {"fields": ("payment_method", "total_amount", "shipping_fee", "status")}),
        ]
        if obj is not None:
            sections.extend(
                [
                    ("Даты", {"fields": ("placed_at",)}),
                    ("Склад", {"fields": ("inventory_impact_display",)}),
                ]
            )
        return tuple(sections)

    @admin.display(description="Влияние на склад")
    def inventory_impact_display(self, obj):
        if obj is None:
            return "—"
        transactions = obj.inventory_transactions.all().select_related("product")
        if not transactions:
            return format_html("<em>Операций по складу нет</em>")
        html = '<table style="width:100%; border-collapse: collapse;">'
        html += '<tr style="background: #f0f0f0;"><th style="padding:8px; text-align:left;">Товар</th><th style="padding:8px; text-align:center;">Изменение</th><th style="padding:8px; text-align:center;">Было</th><th style="padding:8px; text-align:center;">Стало</th></tr>'
        for trans in transactions:
            html += f"<tr><td style=\"padding:8px; border-top:1px solid #ddd;\">{trans.product.name}</td>"
            html += f"<td style=\"padding:8px; border-top:1px solid #ddd; text-align:center; color:red; font-weight:bold;\">{trans.quantity_change:+d}</td>"
            html += f"<td style=\"padding:8px; border-top:1px solid #ddd; text-align:center;\">{trans.stock_before}</td>"
            html += f"<td style=\"padding:8px; border-top:1px solid #ddd; text-align:center;\">{trans.stock_after}</td></tr>"
        html += "</table>"
        return format_html(html)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path("order-history/", self.admin_site.admin_view(self.order_history_view), name="order-history"),
        ]
        return custom_urls + urls

    def order_history_view(self, request):
        from django.db.models.functions import TruncMonth

        all_orders = Order.objects.all().select_related("user").prefetch_related("items__product").order_by("-placed_at")
        total_orders = all_orders.count()
        total_revenue = all_orders.aggregate(Sum("total_amount"))["total_amount__sum"] or 0
        orders_by_status = list(
            all_orders.values("status").annotate(count=Count("id"), revenue=Sum("total_amount")).order_by("-count")
        )
        for s in orders_by_status:
            s["status_display"] = dict(Order.STATUS_CHOICES).get(s["status"], s["status"])
        recent_orders = all_orders[:50]
        monthly_orders = (
            all_orders.annotate(month=TruncMonth("placed_at"))
            .values("month")
            .annotate(orders=Count("id"), revenue=Sum("total_amount"))
            .order_by("-month")[:12]
        )
        top_customers = (
            all_orders.filter(user__isnull=False)
            .values("user__email")
            .annotate(order_count=Count("id"), total_spent=Sum("total_amount"))
            .order_by("-total_spent")[:10]
        )

        context = dict(
            self.admin_site.each_context(request),
            recent_orders=recent_orders,
            total_orders=total_orders,
            total_revenue=total_revenue,
            orders_by_status=orders_by_status,
            monthly_orders=monthly_orders,
            top_customers=top_customers,
            title="История заказов и аналитика",
        )
        return render(request, "admin/order_history.html", context)


admin.site.index_template = "admin/custom_index.html"
