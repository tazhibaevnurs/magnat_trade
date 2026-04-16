"""Исключения бизнес-логики витрины."""


class InsufficientStockError(Exception):
    """Недостаточно товара на складе при оформлении заказа."""

    def __init__(self, product_name: str, available: int):
        self.product_name = product_name
        self.available = available
        super().__init__(f"{product_name}: доступно {available}")
