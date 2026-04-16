"""Общие фикстуры для pytest-django."""

from __future__ import annotations

import pytest
from django.test import override_settings
from rest_framework.test import APIClient


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def integration_key() -> str:
    return "test-integration-api-key"


@pytest.fixture(autouse=True)
def _integration_and_celery_settings(settings, integration_key):
    settings.INTEGRATION_API_KEY = integration_key
    settings.PAYMENT_WEBHOOK_SECRET = "test-webhook-hmac-secret"
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "pytest-magnat",
        }
    }
    settings.ONEC_API_BASE_URL = ""


@pytest.fixture
def integration_headers(integration_key) -> dict[str, str]:
    return {"HTTP_X_API_KEY": integration_key}


# --- Коды как в 1С (строковые id) ---

@pytest.fixture
def cat_id() -> str:
    return "НФ-CAT-TEST-000001"


@pytest.fixture
def product_id() -> str:
    return "НФ-PRD-TEST-000002"


@pytest.fixture
def external_user_id() -> str:
    return "НФ-USR-TEST-000003"


@pytest.fixture
def category(db, cat_id):
    from products.models import Category
    from products.repositories.category_repository import _unique_category_slug

    name = "Тестовая категория"
    return Category.objects.create(
        id=cat_id,
        slug=_unique_category_slug(cat_id, name),
        name=name,
        parent=None,
        is_active=True,
    )


@pytest.fixture
def product(db, category, product_id):
    from products.models import Product

    return Product.objects.create(
        id=product_id,
        sku="TEST-SKU-1",
        name="Тестовый товар",
        category=category,
        retail_price="100.00",
        wholesale_price="80.00",
        stock=50,
        unit="pcs",
        is_active=True,
    )


@pytest.fixture
def user_with_external(db, external_user_id):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return User.objects.create_user(
        email="buyer@test.local",
        password="test-pass-123",
        external_id=external_user_id,
        user_type="retail",
        entity_type="individual",
    )


@pytest.fixture
def order_with_items(db, user_with_external, product, product_id):
    from decimal import Decimal

    from orders.models import Order, OrderItem

    order = Order.objects.create(
        user=user_with_external,
        total_amount=Decimal("200.00"),
        status="pending",
        payment_status="pending",
        delivery_status="pending",
        currency="KGS",
        price_type="retail",
    )
    OrderItem.objects.create(
        order=order,
        product_id=product_id,
        quantity=2,
        price=Decimal("100.00"),
        name_snapshot=product.name,
    )
    return order
