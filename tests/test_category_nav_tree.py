"""Дерево навигации каталога (полная вложенность subs)."""

from __future__ import annotations

import pytest

from shop.category_nav import filter_category_nav
from shop.models import Category


@pytest.mark.django_db
def test_build_category_nav_nested_tree():
    from shop.category_nav import build_category_nav_payload

    root = Category.objects.create(name="Школа", slug="school-root")
    mid = Category.objects.create(name="Тетради", slug="school-notebooks", parent=root)
    leaf = Category.objects.create(name="Тетради 12л", slug="school-nb-12", parent=mid)

    payload = build_category_nav_payload([root], allowed_descendant_slugs=None)
    assert len(payload) == 1
    assert payload[0]["slug"] == root.slug
    assert len(payload[0]["subs"]) == 1
    assert payload[0]["subs"][0]["slug"] == mid.slug
    assert len(payload[0]["subs"][0]["subs"]) == 1
    assert payload[0]["subs"][0]["subs"][0]["slug"] == leaf.slug


def test_filter_category_nav_deep_match():
    payload = [
        {
            "slug": "r",
            "name": "Root",
            "subs": [
                {
                    "slug": "m",
                    "name": "Mid",
                    "subs": [{"slug": "l", "name": "Лист только здесь", "subs": []}],
                }
            ],
        }
    ]
    out = filter_category_nav(payload, "лист")
    assert len(out) == 1
    assert out[0]["subs"][0]["subs"][0]["slug"] == "l"


def test_filter_category_nav_root_keeps_full_subtree_when_name_matches():
    payload = [
        {
            "slug": "r",
            "name": "Школа",
            "subs": [{"slug": "m", "name": "Тетради", "subs": [{"slug": "x", "name": "X", "subs": []}]}],
        }
    ]
    out = filter_category_nav(payload, "школа")
    assert len(out) == 1
    assert len(out[0]["subs"]) == 1
