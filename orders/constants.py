"""Префикс строки позиции для демо-товаров витрины (shop.Product) внутри orders.OrderItem.product_id."""

DEMO_PRODUCT_LINE_PREFIX = "DEMO:"


def is_demo_line_product_id(product_id: str) -> bool:
    return str(product_id).startswith(DEMO_PRODUCT_LINE_PREFIX)


def demo_shop_product_pk(product_id: str) -> int | None:
    if not is_demo_line_product_id(product_id):
        return None
    try:
        return int(str(product_id).split(":", 1)[1])
    except (IndexError, ValueError):
        return None
