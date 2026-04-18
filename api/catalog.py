"""Публичное чтение каталога."""

from __future__ import annotations

from rest_framework import serializers
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny

from products.models import Category, Product


class CategoryOutSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "parent_id", "is_active", "updated_at")


class ProductOutSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = (
            "id",
            "sku",
            "name",
            "category_id",
            "retail_price",
            "wholesale_price",
            "stock",
            "unit",
            "is_active",
            "updated_at",
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None
        from shop.pricing import user_sees_wholesale_prices

        if not user_sees_wholesale_prices(user):
            data.pop("wholesale_price", None)
        return data


class CategoryListView(ListAPIView):
    serializer_class = CategoryOutSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return Category.objects.filter(is_active=True).order_by("name")


class ProductListView(ListAPIView):
    serializer_class = ProductOutSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = (
            Product.objects.filter(is_active=True)
            .select_related("category")
            .order_by("name")
        )
        cat = self.request.query_params.get("category_id")
        if cat:
            qs = qs.filter(category_id=cat)
        raw = (self.request.query_params.get("in_stock") or "").strip().lower()
        if raw in ("1", "true", "on", "yes"):
            qs = qs.filter(stock__gt=0)
        return qs


class ProductDetailView(RetrieveAPIView):
    serializer_class = ProductOutSerializer
    permission_classes = [AllowAny]
    lookup_field = "pk"

    def get_queryset(self):
        return Product.objects.select_related("category").filter(is_active=True)
