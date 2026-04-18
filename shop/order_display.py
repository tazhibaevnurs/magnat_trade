"""Отображение строк единого заказа (orders.Order) в шаблонах."""

from __future__ import annotations

from orders.constants import demo_shop_product_pk
from products.models import Product as CatalogProduct
from shop.models import Product as ShopProduct


def attach_line_display_products(order) -> None:
    """На каждый OrderItem вешает display_product (демо или каталог 1С)."""
    for item in order.items.all():
        demo_pk = demo_shop_product_pk(item.product_id)
        if demo_pk is not None:
            item.display_product = ShopProduct.objects.filter(pk=demo_pk).first()
        else:
            item.display_product = CatalogProduct.objects.filter(pk=item.product_id).first()
