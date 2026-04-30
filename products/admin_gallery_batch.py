"""Батчевая загрузка изображений каталога (products.ProductImage) из админки."""

from __future__ import annotations

import os
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Max

from products.models import Product, ProductImage

_ALLOWED_EXT = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif"})


def max_files_per_request() -> int:
    return int(getattr(settings, "PRODUCT_GALLERY_UPLOAD_MAX_FILES_PER_REQUEST", 24))


def max_file_bytes() -> int:
    return int(getattr(settings, "PRODUCT_GALLERY_UPLOAD_MAX_FILE_BYTES", 8 * 1024 * 1024))


def validate_catalog_image_upload(file: Any) -> None:
    name = getattr(file, "name", "") or ""
    ext = os.path.splitext(str(name).lower())[1]
    if ext not in _ALLOWED_EXT:
        raise ValidationError(
            "Допустимые форматы: " + ", ".join(sorted(_ALLOWED_EXT)),
        )
    size = getattr(file, "size", None)
    lim = max_file_bytes()
    if size is not None and size > lim:
        mb = lim // (1024 * 1024)
        raise ValidationError(f"Размер файла не более {mb} МБ.")


def append_images_for_product(product: Product, files: list[Any]) -> tuple[int, list[dict[str, str]]]:
    """Создаёт записи галереи; при ошибке по файлу запись пропускается, ошибка попадает в список."""
    errors: list[dict[str, str]] = []
    created = 0

    max_so = product.images.aggregate(m=Max("sort_order"))["m"]
    order = (max_so if max_so is not None else -1) + 1

    for f in files:
        fname = getattr(f, "name", "") or "file"
        try:
            validate_catalog_image_upload(f)
            ProductImage.objects.create(product=product, image=f, sort_order=order)
            order += 1
            created += 1
        except ValidationError as e:
            errors.append(
                {"name": fname, "detail": "; ".join(getattr(e, "messages", []) or [str(e)])},
            )
        except Exception as exc:
            errors.append({"name": fname, "detail": str(exc)})

    return created, errors
