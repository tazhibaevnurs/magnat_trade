"""Разбор categoryProductList (плоский и вложенный форматы)."""

from __future__ import annotations

import pytest

from integrations.parsers.category_product_tree import (
    normalize_product_name_key,
    parse_category_product_payload,
)


@pytest.fixture
def sample_nested_payload() -> dict:
    return {
        "Сайт": [
            {
                "Группа А": [
                    {"Подгруппа 1": ["Товар один", "Товар два"]},
                ]
            },
            {"Группа Б": [{"Лист": ["Другой товар"]}]},
        ]
    }


@pytest.fixture
def sample_flat_payload() -> list:
    return [
        {
            "id": "CAT-001",
            "name": "Раздел 1",
            "products": ["Товар A", {"name": "Товар B"}],
        }
    ]


def test_normalize_product_name_key():
    assert normalize_product_name_key("  Товар  один  ") == normalize_product_name_key("Товар один")


def test_parse_nested(sample_nested_payload):
    cats, name_map, root_ids = parse_category_product_payload(sample_nested_payload)
    assert len(root_ids) == 2
    assert normalize_product_name_key("Товар один") in name_map


def test_parse_flat(sample_flat_payload):
    cats, name_map, root_ids = parse_category_product_payload(sample_flat_payload)
    assert len(cats) == 1
    assert root_ids == ["CAT-001"]
    assert normalize_product_name_key("Товар A") in name_map


def test_parse_empty():
    cats, name_map, root_ids = parse_category_product_payload({})
    assert cats == [] and name_map == {} and root_ids == []
