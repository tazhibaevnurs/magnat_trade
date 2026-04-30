"""Синхронизация категорий, товаров, клиентов (интеграция 1С)."""

from __future__ import annotations

import uuid

import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestCategorySync:
    def test_creates_category(self, api_client, integration_headers, cat_id):
        url = reverse("api-categories-sync")
        payload = [
            {
                "id": str(cat_id),
                "name": "Бумага",
                "parent_id": None,
                "is_active": True,
            }
        ]
        r = api_client.post(url, payload, format="json", **integration_headers)
        assert r.status_code == 200
        assert r.json() == {"created": 1, "updated": 0, "total": 1}

        from products.models import Category

        c = Category.objects.get(id=cat_id)
        assert c.name == "Бумага"

    def test_wrapped_items_key(self, api_client, integration_headers, cat_id):
        url = reverse("api-categories-sync")
        r = api_client.post(
            url,
            {"items": [{"id": str(cat_id), "name": "X", "parent_id": None}]},
            format="json",
            **integration_headers,
        )
        assert r.status_code == 200

    def test_rejects_without_api_key(self, api_client, cat_id):
        url = reverse("api-categories-sync")
        r = api_client.post(
            url,
            [{"id": str(cat_id), "name": "X", "parent_id": None}],
            format="json",
        )
        assert r.status_code in (401, 403)


@pytest.mark.django_db
class TestProductSync:
    def test_creates_product(self, api_client, integration_headers, category, product_id):
        url = reverse("api-products-sync")
        payload = [
            {
                "id": str(product_id),
                "sku": "SKU-NEW",
                "name": "Новый товар",
                "category_id": str(category.id),
                "prices": {"retail": 10.5, "wholesale": 9.0},
                "stock": 5,
                "unit": "pcs",
                "is_active": True,
            }
        ]
        r = api_client.post(url, payload, format="json", **integration_headers)
        assert r.status_code == 200
        assert r.json()["created"] == 1

        from products.models import Product

        p = Product.objects.get(id=product_id)
        assert p.sku == "SKU-NEW"
        assert p.category_id == category.id

    def test_idempotent_update_by_uuid_only(
        self, api_client, integration_headers, category, product_id
    ):
        from products.models import Product

        url = reverse("api-products-sync")
        body = [
            {
                "id": str(product_id),
                "sku": "SKU-A",
                "name": "Имя 1",
                "category_id": str(category.id),
                "prices": {"retail": 1.0, "wholesale": 1.0},
                "stock": 1,
            }
        ]
        api_client.post(url, body, format="json", **integration_headers)
        body[0]["name"] = "Имя 2"
        body[0]["sku"] = "SKU-B"
        r = api_client.post(url, body, format="json", **integration_headers)
        assert r.status_code == 200
        assert r.json()["updated"] == 1
        p = Product.objects.get(id=product_id)
        assert p.name == "Имя 2"
        assert p.sku == "SKU-B"

    def test_sync_leaves_manual_description_intact(
        self, api_client, integration_headers, category, product_id
    ):
        """Ручное описание в БД не должно затираться апдейтом из 1С (поле не входит в defaults)."""
        from products.models import Product

        url = reverse("api-products-sync")
        body = [
            {
                "id": str(product_id),
                "sku": "SKU-X",
                "name": "Товар А",
                "category_id": str(category.id),
                "prices": {"retail": 1.0, "wholesale": 1.0},
                "stock": 1,
            }
        ]
        api_client.post(url, body, format="json", **integration_headers)
        manual = "Текст описания только для сайта — не из 1С."
        Product.objects.filter(pk=product_id).update(description=manual)

        body[0]["name"] = "Товар Б переименован"
        r = api_client.post(url, body, format="json", **integration_headers)
        assert r.status_code == 200

        p = Product.objects.get(id=product_id)
        assert p.name == "Товар Б переименован"
        assert p.description == manual


@pytest.mark.django_db
class TestCustomerSync:
    def test_upsert_by_external_id(self, api_client, integration_headers, external_user_id):
        url = reverse("api-customers-sync")
        payload = [
            {
                "id": str(external_user_id),
                "email": "synced@test.local",
                "name": "Петр Петров",
                "phone": "+996700000000",
                "price_type": "wholesale",
                "entity_type": "legal_entity",
                "is_active": True,
            }
        ]
        r = api_client.post(url, payload, format="json", **integration_headers)
        assert r.status_code == 200
        assert r.json()["total"] == 1

        from django.contrib.auth import get_user_model

        u = get_user_model().objects.get(external_id=external_user_id)
        assert u.email == "synced@test.local"
        assert u.user_type == "wholesale"

        payload[0]["email"] = "synced@test.local"
        payload[0]["name"] = "Новое имя"
        r2 = api_client.post(url, payload, format="json", **integration_headers)
        assert r2.json()["updated"] == 1
        u.refresh_from_db()
        assert u.first_name == "Новое"


@pytest.mark.django_db
class TestIdempotencyKey:
    def test_replays_identical_request(self, api_client, integration_headers, cat_id):
        url = reverse("api-categories-sync")
        body = [{"id": str(cat_id), "name": "Idem", "parent_id": None}]
        key = str(uuid.uuid4())
        headers = {**integration_headers, "HTTP_IDEMPOTENCY_KEY": key}
        r1 = api_client.post(url, body, format="json", **headers)
        assert r1.status_code == 200
        r2 = api_client.post(url, body, format="json", **headers)
        assert r2.status_code == 200
        assert r2["X-Idempotent-Replayed"] == "true"
        assert r1.json() == r2.json()
