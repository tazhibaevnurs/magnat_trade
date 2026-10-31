import pytest
from django.core.cache import cache


@pytest.mark.django_db
def test_cache_get_default_when_missing(settings):
    settings.CACHES = {
        "default": {
            "BACKEND": "magnat_trade_project.cache_backends.ResilientRedisCache",
            "LOCATION": "redis://127.0.0.1:6399/0",
        }
    }
    from django.core.cache import caches

    backend = caches["default"]
    assert backend.get("missing-key", default=[]) == []
