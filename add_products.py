#!/usr/bin/env python
"""Заполнение каталога демо-данными (канцелярия). Запуск: python add_products.py"""
import io
import os
import sys
import urllib.error
import urllib.request

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "magnat_trade_project.settings")
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from decimal import Decimal

from django.core.files.base import ContentFile

from shop.models import Category, Product, ProductImage


def _pillow_gradient_jpeg(slug: str, width: int = 800, height: int = 1000) -> bytes:
    """Офлайн-заглушка: градиент JPEG, цвета уникальны для slug."""
    from hashlib import sha256

    from PIL import Image, ImageDraw

    h = sha256(slug.encode()).digest()
    r1, g1, b1 = h[0], h[1], h[2]
    r2, g2, b2 = h[8], h[9], h[10]
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)
    for y in range(height):
        t = y / max(height - 1, 1)
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return buf.getvalue()


def _download_picsum_jpeg(picsum_id: int, width: int = 800, height: int = 1000) -> bytes | None:
    url = f"https://picsum.photos/id/{picsum_id}/{width}/{height}"
    req = urllib.request.Request(url, headers={"User-Agent": "MagnatTrade/1.0 (add_products)"})
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return resp.read()
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


def ensure_product_image(product: Product, picsum_id: int) -> None:
    """Одно основное фото на товар; при повторном запуске заменяется."""
    product.images.all().delete()
    data = _download_picsum_jpeg(picsum_id)
    if not data:
        data = _pillow_gradient_jpeg(product.slug)
        name = f"{product.slug}_local.jpg"
    else:
        name = f"{product.slug}.jpg"
    ProductImage.objects.create(
        product=product,
        image=ContentFile(data, name=name),
        alt=product.name,
        sort_order=0,
    )


def run():
    pens, _ = Category.objects.get_or_create(
        slug="premium-pens",
        defaults={"name": "Премиальные ручки"},
    )
    paper, _ = Category.objects.get_or_create(
        slug="sketch-paper",
        defaults={"name": "Бумага для эскизов"},
    )
    office, _ = Category.objects.get_or_create(
        slug="office-sets",
        defaults={"name": "Офисные наборы"},
    )
    roller, _ = Category.objects.get_or_create(
        slug="rollerballs",
        defaults={"name": "Роллеры и гелевые", "parent": pens},
    )

    demo = [
        {
            "name": "Ручка перьевая Magnat Noir",
            "slug": "magnat-noir-fountain",
            "description": "Перьевая ручка с латунным корпусом и иридиевым пером. Плавная подача чернил, идеально для подписей и эскизов.",
            "category": pens,
            "price": Decimal("4200.00"),
            "discount_price": Decimal("3590.00"),
            "stock": 28,
            "is_featured": True,
            "is_bestseller": True,
            "picsum_id": 24,
        },
        {
            "name": "Набор гелевых ручек Studio 12",
            "slug": "studio-12-gel-set",
            "description": "12 насыщенных цветов, быстросохнущие чернила, эргономичный хват.",
            "category": pens,
            "price": Decimal("890.00"),
            "discount_price": None,
            "stock": 60,
            "is_featured": True,
            "is_bestseller": False,
            "picsum_id": 48,
        },
        {
            "name": "Роллер Graphite Pro",
            "slug": "graphite-pro-roller",
            "description": "Линия 0.5 мм, герметичный колпачок, корпус из анодированного алюминия.",
            "category": roller,
            "price": Decimal("2100.00"),
            "discount_price": None,
            "stock": 40,
            "is_featured": False,
            "is_bestseller": True,
            "picsum_id": 106,
        },
        {
            "name": "Скетчбук A4 «Плотная бумага»",
            "slug": "sketchbook-a4-heavy",
            "description": "200 г/м², 40 листов, кольцевой механизм, слой под маркер и акварель.",
            "category": paper,
            "price": Decimal("1450.00"),
            "discount_price": Decimal("1190.00"),
            "stock": 45,
            "is_featured": True,
            "is_bestseller": True,
            "picsum_id": 103,
        },
        {
            "name": "Блок для эскизов A5",
            "slug": "sketch-pad-a5",
            "description": "Плотная бумага для эскизов, мягкая обложка, 80 листов.",
            "category": paper,
            "price": Decimal("680.00"),
            "discount_price": None,
            "stock": 100,
            "is_featured": False,
            "is_bestseller": False,
            "picsum_id": 367,
        },
        {
            "name": "Офисный набор Executive",
            "slug": "office-set-executive",
            "description": "Лоток для бумаги, держатель для ручек, стикеры, скрепки в стильном кейсе.",
            "category": office,
            "price": Decimal("5200.00"),
            "discount_price": None,
            "stock": 15,
            "is_featured": True,
            "is_bestseller": False,
            "picsum_id": 180,
        },
        {
            "name": "Набор для рабочего стола Minimal",
            "slug": "desk-set-minimal",
            "description": "Матовый металл, органайзер для канцелярии и карандашница.",
            "category": office,
            "price": Decimal("3100.00"),
            "discount_price": Decimal("2790.00"),
            "stock": 22,
            "is_featured": False,
            "is_bestseller": True,
            "picsum_id": 201,
        },
    ]

    for row in demo:
        picsum_id = row.pop("picsum_id")
        product, created = Product.objects.update_or_create(
            slug=row["slug"],
            defaults={
                "name": row["name"],
                "description": row["description"],
                "category": row["category"],
                "price": row["price"],
                "discount_price": row["discount_price"],
                "stock": row["stock"],
                "is_featured": row["is_featured"],
                "is_bestseller": row["is_bestseller"],
                "is_active": True,
            },
        )
        ensure_product_image(product, picsum_id)
        print(f"{'+' if created else '~'} {product.name} (фото)")


if __name__ == "__main__":
    run()
