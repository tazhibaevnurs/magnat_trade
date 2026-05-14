"""Цены каталога 1С: розница для гостей и всех с user_type=retail; опт только при user_type=wholesale (после одобрения заявки)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


def user_sees_wholesale_prices(user: AbstractUser | None) -> bool:
    return bool(
        user
        and user.is_authenticated
        and getattr(user, "user_type", "retail") == "wholesale"
    )


def catalog_unit_price(catalog_product, user: AbstractUser | None):
    """Цена строки каталога: поля модели совпадают с ключами JSON 1С (retail / wholesale).

    Розничная сумма всегда из ``retail_price``, оптовая — из ``wholesale_price``.
    У менеджеров и розницы — розничное поле; у одобренного опта — оптовое.
    """
    if user_sees_wholesale_prices(user):
        return catalog_product.wholesale_price
    return catalog_product.retail_price


def is_manager(user: AbstractUser | None) -> bool:
    """Бизнес-роль «менеджер» в каталоге (цены как у розницы)."""
    return bool(
        user
        and user.is_authenticated
        and getattr(user, "user_type", "retail") == "manager"
    )


def can_access_manager_panel(user: AbstractUser | None) -> bool:
    """
    Панель заявок на опт и управление: менеджер по полю user_type,
    либо персонал Django (is_staff), либо суперпользователь.
    """
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "is_superuser", False):
        return True
    if getattr(user, "is_staff", False):
        return True
    return getattr(user, "user_type", "retail") == "manager"
