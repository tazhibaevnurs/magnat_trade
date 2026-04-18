"""Отображение товаров из интеграции 1С (products.Product) на витрине shop."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Type

from django.core.cache import cache
from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.db.models import Case, IntegerField, Q, Value, When
from django.urls import reverse

from products.models import Category as CatalogCategory
from products.models import Product as CatalogProduct

from .pricing import user_sees_wholesale_prices

_CATALOG_EXISTS_CACHE_KEY = "shop:catalog_products_exist"
_CATALOG_EXISTS_TTL = 60


def _catalog_products_exist_query() -> bool:
    return CatalogProduct.objects.filter(is_active=True).exists()


def in_stock_only_from_request(request) -> bool:
    """GET-параметр in_stock=1 (чекбокс «только в наличии»)."""
    return request.GET.get("in_stock", "").strip().lower() in ("1", "true", "on", "yes")


def catalog_products_exist() -> bool:
    """Кэш на минуту — снижает повторные EXISTS на горячих страницах витрины."""
    return cache.get_or_set(
        _CATALOG_EXISTS_CACHE_KEY,
        _catalog_products_exist_query,
        _CATALOG_EXISTS_TTL,
    )


def expand_category_slugs_including_descendants(
    slugs: list[str],
    CategoryModel: Type[models.Model],
) -> list[str]:
    """Slug'и выбранных разделов плюс все вложенные: товары только в подкатегориях тоже попадают в выборку."""
    cleaned = [s.strip() for s in slugs if s and str(s).strip()]
    if not cleaned:
        return []
    roots = list(CategoryModel.objects.filter(slug__in=cleaned))
    if not roots:
        return cleaned
    try:
        CategoryModel._meta.get_field("is_active")
    except FieldDoesNotExist:
        has_active = False
    else:
        has_active = True
    out: set[str] = set()
    frontier = list(roots)
    while frontier:
        cat = frontier.pop()
        out.add(cat.slug)
        ch_qs = cat.children.all()
        if has_active:
            ch_qs = ch_qs.filter(is_active=True)
        frontier.extend(list(ch_qs))
    return list(out)


def filter_catalog_products(
    request, *, promotions_only: bool = False, new_arrivals_only: bool = False
) -> Any:
    """QuerySet товаров 1С с теми же GET-фильтрами, что и у витрины.

    При ``promotions_only=True`` — только товары из ``PromotionItem`` (1С).
    При ``new_arrivals_only=True`` — только товары из ``NewArrivalItem`` (1С).
    Если соответствующий список в БД пуст — пустой queryset.
    """
    from shop.services.new_arrival_items import catalog_new_arrival_product_ids_ordered
    from shop.services.promotion_items import catalog_promotion_product_ids_ordered

    qs = CatalogProduct.objects.filter(is_active=True).select_related("category").prefetch_related("images")

    if promotions_only and new_arrivals_only:
        return CatalogProduct.objects.none()

    if promotions_only:
        id_list = catalog_promotion_product_ids_ordered()
        if not id_list:
            return CatalogProduct.objects.none()
        qs = qs.filter(pk__in=id_list)
    elif new_arrivals_only:
        id_list = catalog_new_arrival_product_ids_ordered()
        if not id_list:
            return CatalogProduct.objects.none()
        qs = qs.filter(pk__in=id_list)

    wholesale = user_sees_wholesale_prices(request.user)
    price_field = "wholesale_price" if wholesale else "retail_price"

    search_query = request.GET.get("search", "").strip()
    if search_query:
        qs = qs.filter(Q(name__icontains=search_query) | Q(sku__icontains=search_query))

    selected_categories = [c for c in request.GET.getlist("categories") if c]
    if selected_categories:
        expanded = expand_category_slugs_including_descendants(selected_categories, CatalogCategory)
        qs = qs.filter(category__slug__in=expanded)

    price_min = request.GET.get("price_min", "").strip()
    price_max = request.GET.get("price_max", "").strip()
    try:
        if price_min:
            qs = qs.filter(**{f"{price_field}__gte": Decimal(price_min)})
        if price_max:
            qs = qs.filter(**{f"{price_field}__lte": Decimal(price_max)})
    except (InvalidOperation, ValueError):
        pass

    if in_stock_only_from_request(request):
        qs = qs.filter(stock__gt=0)

    sort_by = request.GET.get("sort_by", "name")
    if sort_by == "a-to-z" or sort_by == "name":
        qs = qs.order_by("name")
    elif sort_by == "z-to-a":
        qs = qs.order_by("-name")
    elif sort_by == "price-lowest-first":
        qs = qs.order_by(price_field, "name")
    elif sort_by == "price-highest-first":
        qs = qs.order_by(f"-{price_field}", "name")
    elif sort_by == "recently-added":
        qs = qs.order_by("-updated_at")
    elif sort_by == "in-stock-first":
        qs = qs.annotate(
            _sort_in_stock=Case(
                When(stock__gt=0, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        ).order_by("_sort_in_stock", "-stock", "name")
    else:
        qs = qs.order_by("name")

    return qs


class CatalogProductDisplay:
    """Адаптер под шаблоны карточки (shop Product: price, image_url, get_absolute_url)."""

    __slots__ = ("_p", "_user")

    def __init__(self, p: CatalogProduct, *, user=None) -> None:
        self._p = p
        self._user = user

    @property
    def id(self) -> str:
        return str(self._p.pk)

    @property
    def name(self) -> str:
        return self._p.name

    @property
    def price(self):
        from .pricing import catalog_unit_price

        return catalog_unit_price(self._p, self._user)

    @property
    def discount_price(self):
        return None

    @property
    def current_price(self):
        from .pricing import catalog_unit_price

        return catalog_unit_price(self._p, self._user)

    @property
    def stock(self) -> int:
        return int(self._p.stock)

    @property
    def is_active(self) -> bool:
        return self._p.is_active

    @property
    def image_url(self) -> str:
        return self._p.image_url

    @property
    def gallery_urls(self) -> list[str]:
        return list(self._p.gallery_urls)

    @property
    def is_catalog_product(self) -> bool:
        return True

    @property
    def measure_line(self) -> str:
        u = (getattr(self._p, "unit", "") or "").strip().lower()
        if u in ("pcs", "шт", "шт.", ""):
            return "1 шт"
        if u in ("kg", "кг"):
            return "1 кг"
        if u in ("g", "г"):
            return "1 г"
        if u in ("l", "л", "l."):
            return "1 л"
        return f"1 {self._p.unit}"

    def get_absolute_url(self) -> str:
        return reverse("catalog_pdp", kwargs={"product_id": self._p.pk})
