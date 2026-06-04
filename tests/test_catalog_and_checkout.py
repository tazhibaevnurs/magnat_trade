"""Публичный каталог и checkout."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestCatalog:
    def test_categories_list(self, api_client, category):
        url = reverse("api-catalog-categories")
        r = api_client.get(url)
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        assert str(category.id) in {str(x["id"]) for x in data}

    def test_products_list_filter_by_category(self, api_client, product, category):
        url = reverse("api-catalog-products")
        r = api_client.get(url, {"category_id": str(category.id)})
        assert r.status_code == 200
        ids = {str(x["id"]) for x in r.json()}
        assert str(product.id) in ids

    def test_product_detail(self, api_client, product):
        url = reverse("api-catalog-product-detail", kwargs={"pk": product.id})
        r = api_client.get(url)
        assert r.status_code == 200
        assert r.json()["sku"] == product.sku

    def test_api_hides_wholesale_price_for_anonymous(self, api_client, product):
        url = reverse("api-catalog-products")
        r = api_client.get(url)
        assert r.status_code == 200
        row = next(x for x in r.json() if x["id"] == str(product.id))
        assert "wholesale_price" not in row
        assert row["retail_price"] == "100.00"

    def test_api_hides_wholesale_price_for_retail_user(self, api_client, product, user_with_external):
        api_client.force_login(user_with_external)
        url = reverse("api-catalog-products")
        r = api_client.get(url)
        assert r.status_code == 200
        row = next(x for x in r.json() if x["id"] == str(product.id))
        assert "wholesale_price" not in row

    def test_api_includes_wholesale_for_approved_wholesale_user(
        self, api_client, product, user_wholesale_approved
    ):
        api_client.force_login(user_wholesale_approved)
        url = reverse("api-catalog-products")
        r = api_client.get(url)
        assert r.status_code == 200
        row = next(x for x in r.json() if x["id"] == str(product.id))
        assert row["wholesale_price"] == "80.00"

    def test_api_product_detail_hides_wholesale_for_guest(self, api_client, product):
        url = reverse("api-catalog-product-detail", kwargs={"pk": product.id})
        r = api_client.get(url)
        assert r.status_code == 200
        assert "wholesale_price" not in r.json()


@pytest.mark.django_db
class TestCheckout:
    def test_requires_authentication(self, api_client, product):
        url = reverse("api-checkout-order")
        r = api_client.post(
            url,
            {
                "items": [{"product_id": str(product.id), "quantity": 1}],
                "price_type": "retail",
            },
            format="json",
        )
        assert r.status_code == 403

    def test_requires_external_id_when_onec_configured(self, api_client, product, settings):
        settings.ONEC_API_BASE_URL = "https://example.test/bereke/hs"
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(
            email="noexternal@test.local",
            password="test-pass-123",
            external_id=None,
        )
        api_client.force_login(user)
        url = reverse("api-checkout-order")
        r = api_client.post(
            url,
            {
                "items": [{"product_id": str(product.id), "quantity": 1}],
                "price_type": "retail",
            },
            format="json",
        )
        assert r.status_code == 400
        assert "1С" in (r.json().get("detail") or "")

    def test_creates_order_and_payment_url(self, api_client, user_with_external, product):
        api_client.force_login(user_with_external)
        url = reverse("api-checkout-order")
        r = api_client.post(
            url,
            {
                "items": [{"product_id": str(product.id), "quantity": 2}],
                "price_type": "retail",
                "currency": "KGS",
            },
            format="json",
        )
        assert r.status_code == 201
        body = r.json()
        assert "order_id" in body
        assert "payment_url" in body
        assert "payment_id" in body

        from orders.models import Order

        o = Order.objects.get(id=body["order_id"])
        assert o.items.count() == 1
        assert o.payment_url

        product.refresh_from_db()
        assert product.stock == 48

    def test_checkout_rejects_wholesale_without_approval(self, api_client, product, user_with_external):
        api_client.force_login(user_with_external)
        url = reverse("api-checkout-order")
        r = api_client.post(
            url,
            {
                "items": [{"product_id": str(product.id), "quantity": 1}],
                "price_type": "wholesale",
                "currency": "KGS",
            },
            format="json",
        )
        assert r.status_code == 400
        payload = str(r.json())
        assert "одобр" in payload.lower() or "price_type" in payload

    def test_checkout_allows_wholesale_after_approval(
        self, api_client, product, user_wholesale_approved
    ):
        api_client.force_login(user_wholesale_approved)
        url = reverse("api-checkout-order")
        r = api_client.post(
            url,
            {
                "items": [{"product_id": str(product.id), "quantity": 1}],
                "price_type": "wholesale",
                "currency": "KGS",
            },
            format="json",
        )
        assert r.status_code == 201
        from orders.models import Order

        order = Order.objects.get(id=r.json()["order_id"])
        assert order.price_type == "wholesale"
        assert order.total_amount == Decimal(str(product.wholesale_price))


@pytest.mark.django_db
class TestShopCategoryDescendants:
    """Выбор родительского раздела в каталоге включает товары из подкатегорий."""

    def test_filter_by_parent_slug_includes_child_category_products(self):
        from django.test import RequestFactory

        from products.models import Category, Product
        from products.repositories.category_repository import _unique_category_slug

        from shop.catalog_display import filter_catalog_products

        parent = Category.objects.create(
            id="НФ-PARENT-DESC-001",
            slug=_unique_category_slug("НФ-PARENT-DESC-001", "Родитель для теста потомков"),
            name="Родитель для теста потомков",
            parent=None,
            is_active=True,
        )
        child = Category.objects.create(
            id="НФ-CHILD-DESC-001",
            slug=_unique_category_slug("НФ-CHILD-DESC-001", "Дочерняя категория"),
            name="Дочерняя категория",
            parent=parent,
            is_active=True,
        )
        Product.objects.create(
            id="НФ-PRD-DESC-001",
            sku="SKU-DESC-1",
            name="Товар только в подкатегории",
            category=child,
            retail_price="10.00",
            wholesale_price="8.00",
            stock=3,
            is_active=True,
        )

        from django.contrib.auth.models import AnonymousUser

        rf = RequestFactory()
        req = rf.get("/shop/", {"categories": parent.slug})
        req.user = AnonymousUser()
        qs = filter_catalog_products(req)
        names = list(qs.values_list("name", flat=True))
        assert "Товар только в подкатегории" in names

    def test_promotions_only_empty_list_returns_no_products(self):
        from django.contrib.auth.models import AnonymousUser
        from django.test import RequestFactory

        from shop.catalog_display import filter_catalog_products

        rf = RequestFactory()
        req = rf.get("/akcii/")
        req.user = AnonymousUser()
        qs = filter_catalog_products(req, promotions_only=True)
        assert qs.count() == 0

    def test_new_arrivals_only_empty_list_returns_no_products(self):
        from django.contrib.auth.models import AnonymousUser
        from django.test import RequestFactory

        from shop.catalog_display import filter_catalog_products

        rf = RequestFactory()
        req = rf.get("/novinki/")
        req.user = AnonymousUser()
        qs = filter_catalog_products(req, new_arrivals_only=True)
        assert qs.count() == 0

    def test_new_arrivals_respects_auto_since_cutoff(self, product):
        from datetime import date

        from django.contrib.auth.models import AnonymousUser
        from django.test import RequestFactory, override_settings

        from shop.catalog_display import filter_catalog_products

        rf = RequestFactory()
        req = rf.get("/novinki/")
        req.user = AnonymousUser()

        future = date(2099, 1, 1)
        with override_settings(SHOP_NEW_ARRIVALS_AUTO_SINCE=future):
            qs_future = filter_catalog_products(req, new_arrivals_only=True)
            assert product.id not in set(qs_future.values_list("pk", flat=True))

        past = date(2020, 1, 1)
        with override_settings(SHOP_NEW_ARRIVALS_AUTO_SINCE=past):
            qs_past = filter_catalog_products(req, new_arrivals_only=True)
            assert product.id in set(qs_past.values_list("pk", flat=True))
