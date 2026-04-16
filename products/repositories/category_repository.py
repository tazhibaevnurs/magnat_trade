from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils.text import slugify

from products.models import Category


def _unique_category_slug(pk: str, name: str) -> str:
    """Стабильный slug для URL; уникален в пределах таблицы."""
    base = slugify(f"{pk}-{name}", allow_unicode=True)[:200]
    if not base:
        base = slugify(pk, allow_unicode=True) or "category"
    slug = base
    n = 0
    while Category.objects.filter(slug=slug).exclude(pk=pk).exists():
        n += 1
        suffix = f"-{n}"
        slug = f"{base[: 220 - len(suffix)]}{suffix}"
    return slug[:220]


class CategoryRepository:
    @staticmethod
    def upsert_from_payload(data: dict[str, Any]) -> tuple[Category, bool]:
        """Идемпотентно создаёт или обновляет категорию по коду из 1С."""
        pk = str(data["id"]).strip()
        name = data["name"]
        defaults = {
            "name": name,
            "slug": _unique_category_slug(pk, name),
            "is_active": data.get("is_active", True),
        }
        parent_id = data.get("parent_id")
        if parent_id is not None and parent_id != "":
            defaults["parent_id"] = str(parent_id).strip()
        else:
            defaults["parent_id"] = None

        with transaction.atomic():
            obj, created = Category.objects.update_or_create(
                id=pk,
                defaults=defaults,
            )
        return obj, created
