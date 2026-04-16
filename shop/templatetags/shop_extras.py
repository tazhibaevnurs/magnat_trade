from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def sum_item_prices(items):
    """Сумма по позициям корзины (цена строки × количество)."""
    total = Decimal("0.00")
    for item in items:
        total += item.total_price()
    return total


@register.filter
def soms(value):
    """Format number as price in сомах (KGS). Always returns 'X.XX сом', never PHP or other currency."""
    if value is None:
        return "0.00 сом"
    try:
        num = float(value)
        return f"{num:.2f} сом"
    except (TypeError, ValueError):
        return "0.00 сом"
