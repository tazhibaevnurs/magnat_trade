"""Подписи корней меню vs .env (SHOP_NAV_ROOT_CATEGORY_NAMES)."""

from shop.category_nav import normalize_nav_root_title


def test_normalize_nav_root_title_strips_trailing_punctuation():
    assert normalize_nav_root_title("Бумага и бумажная продукция.") == normalize_nav_root_title(
        "Бумага и бумажная продукция"
    )


def test_normalize_nav_root_title_collapses_whitespace():
    assert normalize_nav_root_title("Аксессуары") == normalize_nav_root_title("  Аксессуары  ")
