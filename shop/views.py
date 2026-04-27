import json
import mimetypes
import secrets
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import SuspiciousOperation, ValidationError
from django.core.files.storage import default_storage
from django.core.paginator import Paginator
from django.core.validators import validate_email
from django.core.cache import cache
from django.db import transaction
from django.db.models import Case, DecimalField, F, IntegerField, Q, Value, When
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from .category_nav import (
    build_category_nav_payload,
    filter_category_nav,
    get_shop_catalog_nav_roots_and_allowed_slugs,
)
from .catalog_display import (
    CatalogProductDisplay,
    catalog_products_exist,
    expand_category_slugs_including_descendants,
    filter_catalog_products,
    in_stock_only_from_request,
)
from .services.new_arrival_items import shop_new_arrival_product_ids_ordered
from .services.promotion_items import shop_promotion_product_ids_ordered
from .pricing import can_access_manager_panel, catalog_unit_price
from .exceptions import InsufficientStockError
from .models import (
    Address,
    Cart,
    CartItem,
    Category,
    Feedback,
    Product,
    UserProfile,
    WishlistItem,
)
from .order_display import attach_line_display_products
from integrations.services.telegram_notifications import (
    notify_feedback_created,
    notify_order_created,
    notify_wholesale_request_created,
)
from orders.models import Order as CatalogOrder
from products.models import Product as CatalogProduct
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from PIL import Image, UnidentifiedImageError

# Главная: две полные строки при 4 колонках сетки (4 + 4)
LANDING_SECTION_LIMIT = 8
COURIER_SHIPPING_FEE = Decimal("300.00")
FREE_SHIPPING_THRESHOLD = Decimal("3000.00")
MAX_PAGINATION_PAGE = 1000
MAX_CART_ITEM_QTY = 100
MAX_PROFILE_PICTURE_BYTES = 5 * 1024 * 1024
ALLOWED_PROFILE_PICTURE_MIME = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_PROFILE_PICTURE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
POW_TTL_SECONDS = 10 * 60
MAX_SPECIAL_INSTRUCTIONS_LEN = 500


def robots_txt(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /profile/",
        f"Sitemap: {request.build_absolute_uri('/sitemap.xml')}",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")


def sitemap_xml(request):
    urls: list[str] = []
    static_paths = ["/", "/shop/", "/novinki/", "/akcii/", "/about-us/", "/contact-us/"]
    now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    for path in static_paths:
        urls.append(
            f"<url><loc>{request.build_absolute_uri(path)}</loc><lastmod>{now_iso}</lastmod><changefreq>daily</changefreq><priority>0.8</priority></url>"
        )

    for p in Product.objects.filter(is_active=True).only("slug").iterator():
        urls.append(
            f"<url><loc>{request.build_absolute_uri(reverse('pdp', kwargs={'slug': p.slug}))}</loc><changefreq>weekly</changefreq><priority>0.7</priority></url>"
        )
    for p in CatalogProduct.objects.filter(is_active=True).only("id").iterator():
        urls.append(
            f"<url><loc>{request.build_absolute_uri(reverse('catalog_pdp', kwargs={'product_id': p.id}))}</loc><changefreq>weekly</changefreq><priority>0.7</priority></url>"
        )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(urls)
        + "</urlset>"
    )
    return HttpResponse(xml, content_type="application/xml; charset=utf-8")


def _shipping_fee_for_delivery_method(delivery_method: str, subtotal: Decimal) -> Decimal:
    if delivery_method == "courier":
        if subtotal > FREE_SHIPPING_THRESHOLD:
            return Decimal("0.00")
        return COURIER_SHIPPING_FEE
    return Decimal("0.00")


def _sanitize_next_url(request, raw_next: str | None, fallback: str = "/") -> str:
    candidate = (raw_next or "").strip()
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return fallback


def _parse_positive_int_bounded(raw, *, default: int, min_value: int = 1, max_value: int = 100) -> int:
    try:
        val = int(str(raw).strip())
    except (TypeError, ValueError):
        return default
    return max(min_value, min(max_value, val))


def _sanitize_special_instructions(raw: str | None) -> str:
    return (raw or "").strip()[:MAX_SPECIAL_INSTRUCTIONS_LEN]


def _validate_profile_picture_upload(uploaded_file):
    ext = Path(uploaded_file.name or "").suffix.lower()
    if ext not in ALLOWED_PROFILE_PICTURE_EXT:
        raise SuspiciousOperation("Разрешены только изображения JPG, PNG, WEBP и GIF.")
    if uploaded_file.size > MAX_PROFILE_PICTURE_BYTES:
        raise SuspiciousOperation("Размер изображения не должен превышать 5MB.")
    ctype = (getattr(uploaded_file, "content_type", "") or "").lower()
    if ctype and ctype not in ALLOWED_PROFILE_PICTURE_MIME:
        raise SuspiciousOperation("Некорректный MIME-тип файла.")
    pos = uploaded_file.tell()
    uploaded_file.seek(0)
    try:
        img = Image.open(uploaded_file)
        img.verify()
        fmt = (img.format or "").lower()
        if fmt and f".{fmt}" not in ALLOWED_PROFILE_PICTURE_EXT:
            raise SuspiciousOperation("Файл не является валидным изображением.")
    except (UnidentifiedImageError, OSError):
        raise SuspiciousOperation("Файл не является валидным изображением.")
    finally:
        uploaded_file.seek(pos)


def _issue_pow_challenge(purpose: str) -> tuple[str, str]:
    a = secrets.randbelow(8) + 2
    b = secrets.randbelow(8) + 2
    token = secrets.token_urlsafe(18)
    cache.set(f"pow:{purpose}:{token}", str(a + b), timeout=POW_TTL_SECONDS)
    return token, f"Сколько будет {a} + {b}?"


def _verify_pow_challenge(purpose: str, token: str, answer: str) -> bool:
    expected = cache.get(f"pow:{purpose}:{token}")
    if not expected:
        return False
    if str(expected).strip() != str(answer).strip():
        return False
    cache.delete(f"pow:{purpose}:{token}")
    return True


def _unique_products_from_querysets(querysets, limit):
    """Собирает до limit товаров по очереди из querysets без дублей."""
    seen = set()
    out = []
    for qs in querysets:
        for p in qs:
            if p.pk not in seen:
                seen.add(p.pk)
                out.append(p)
                if len(out) >= limit:
                    return out
    return out


def _cart_summary_payload(cart):
    """Сумма корзины и итог без доставки (доставка всегда 0)."""
    if not cart:
        return {
            "subtotal": "0.00",
            "shipping_fee": "0.00",
            "grand_total": "0.00",
            "item_count": 0,
            "line_count": 0,
        }
    subtotal = cart.total_price()
    line_count = cart.items.count()
    ship = Decimal("0.00")
    grand = subtotal + ship
    q = lambda d: str(d.quantize(Decimal("0.01")))
    return {
        "subtotal": q(subtotal),
        "shipping_fee": q(ship),
        "grand_total": q(grand),
        "item_count": cart.item_count(),
        "line_count": line_count,
    }


def _filter_products(request, *, promotions_only=False, new_arrivals_only=False):
    """Фильтрация каталога: поиск, категории (slug), диапазон цены, сортировка."""
    products = (
        Product.objects.filter(is_active=True)
        .select_related("category")
        .prefetch_related("images")
    )

    search_query = request.GET.get("search", "").strip()
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) | Q(description__icontains=search_query)
        )

    selected_categories = [c for c in request.GET.getlist("categories") if c]
    if selected_categories:
        expanded = expand_category_slugs_including_descendants(selected_categories, Category)
        products = products.filter(category__slug__in=expanded)

    products = products.annotate(
        effective_price=Case(
            When(
                discount_price__isnull=False,
                discount_price__lt=F("price"),
                then=F("discount_price"),
            ),
            default=F("price"),
            output_field=DecimalField(max_digits=10, decimal_places=2),
        )
    )

    price_min = request.GET.get("price_min", "").strip()
    price_max = request.GET.get("price_max", "").strip()
    try:
        if price_min:
            products = products.filter(effective_price__gte=Decimal(price_min))
        if price_max:
            products = products.filter(effective_price__lte=Decimal(price_max))
    except (InvalidOperation, ValueError):
        pass

    if in_stock_only_from_request(request):
        products = products.filter(stock__gt=0)

    if promotions_only:
        promoted_ids = shop_promotion_product_ids_ordered()
        if promoted_ids:
            products = products.filter(pk__in=promoted_ids)
        else:
            products = products.filter(discount_price__isnull=False).filter(discount_price__lt=F("price"))

    if new_arrivals_only:
        na_ids = shop_new_arrival_product_ids_ordered()
        products = products.filter(pk__in=na_ids)

    sort_by = request.GET.get("sort_by", "name")
    if sort_by == "a-to-z":
        products = products.order_by("name")
    elif sort_by == "z-to-a":
        products = products.order_by("-name")
    elif sort_by == "price-lowest-first":
        products = products.order_by("effective_price", "name")
    elif sort_by == "price-highest-first":
        products = products.order_by("-effective_price", "name")
    elif sort_by == "recently-added":
        products = products.order_by("-created_at")
    elif sort_by == "in-stock-first":
        products = products.annotate(
            _sort_in_stock=Case(
                When(stock__gt=0, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        ).order_by("_sort_in_stock", "-stock", "name")
    else:
        products = products.order_by("name")

    return products, search_query, selected_categories, sort_by


def _filter_query_string(request) -> str:
    q = request.GET.copy()
    q.pop("page", None)
    return q.urlencode()


def _filter_query_string_from_get(get_dict) -> str:
    q = get_dict.copy()
    q.pop("page", None)
    return q.urlencode()


def _shop_get_with_preset(request, preset: str | None):
    """GET с подстановкой по умолчанию для страниц «Новинки» / «Акции»."""
    defaults: dict[str, str] = {}
    if preset == "new_arrivals":
        defaults = {"sort_by": "recently-added"}
    elif preset == "promotions":
        # Не включаем «только в наличии» по умолчанию: акции — явный список из админки,
        # иначе товар с stock=0 исчезает со страницы.
        defaults = {"sort_by": "price-lowest-first"}
    q = request.GET.copy()
    for key, val in defaults.items():
        if key not in q:
            q[key] = val
    return q


class _ShopFilterRequestProxy:
    __slots__ = ("GET", "user")

    def __init__(self, get_qs, user):
        self.GET = get_qs
        self.user = user


def _shop_context(request, preset: str | None = None):
    """Если в БД есть товары из 1С (products.Product), показываем их; иначе — демо shop.Product."""
    g = _shop_get_with_preset(request, preset)
    filter_req = _ShopFilterRequestProxy(g, request.user)

    if catalog_products_exist():
        qs = filter_catalog_products(
            filter_req,
            promotions_only=(preset == "promotions"),
            new_arrivals_only=(preset == "new_arrivals"),
        )
        paginator = Paginator(qs, 48)
        page_number = _parse_positive_int_bounded(
            g.get("page"),
            default=1,
            min_value=1,
            max_value=MAX_PAGINATION_PAGE,
        )
        page_obj = paginator.get_page(page_number)
        products = [CatalogProductDisplay(p, user=request.user) for p in page_obj.object_list]
        price_min = g.get("price_min", "").strip()
        price_max = g.get("price_max", "").strip()
        breadcrumb_items = [
            {"name": "Главная", "url": "/"},
            {"name": "Магазин", "url": None},
        ]
        return {
            "products": products,
            "page_obj": page_obj,
            "catalog_mode": True,
            "filter_query_string": _filter_query_string_from_get(g),
            "search_query": g.get("search", "").strip(),
            "selected_categories": [c for c in g.getlist("categories") if c],
            "sort_by": g.get("sort_by", "name"),
            "price_min": price_min,
            "price_max": price_max,
            "in_stock": g.get("in_stock") == "1",
            "breadcrumb_items": breadcrumb_items,
        }

    products, search_query, selected_categories, sort_by = _filter_products(
        filter_req,
        promotions_only=(preset == "promotions"),
        new_arrivals_only=(preset == "new_arrivals"),
    )
    price_min = g.get("price_min", "").strip()
    price_max = g.get("price_max", "").strip()
    breadcrumb_items = [
        {"name": "Главная", "url": "/"},
        {"name": "Магазин", "url": None},
    ]
    return {
        "products": products,
        "page_obj": None,
        "catalog_mode": False,
        "filter_query_string": _filter_query_string_from_get(g),
        "search_query": search_query,
        "selected_categories": selected_categories,
        "sort_by": sort_by,
        "price_min": price_min,
        "price_max": price_max,
        "in_stock": g.get("in_stock") == "1",
        "breadcrumb_items": breadcrumb_items,
    }


def landing(request):
    """Homepage (Bazaar-style layout: Top Ratings + New Arrivals)."""
    limit = LANDING_SECTION_LIMIT
    if catalog_products_exist():
        base = CatalogProduct.objects.filter(is_active=True).prefetch_related("images")
        popular_rows = _unique_products_from_querysets(
            (
                base.order_by("-stock", "-updated_at"),
                base.order_by("-updated_at"),
            ),
            limit,
        )
        top_rated_products = [CatalogProductDisplay(p, user=request.user) for p in popular_rows]
        new_rows = _unique_products_from_querysets(
            (
                base.order_by("-updated_at"),
                base.order_by("-stock", "-updated_at"),
            ),
            limit,
        )
        new_arrivals = [CatalogProductDisplay(p, user=request.user) for p in new_rows]
    else:
        from django.utils import timezone
        from datetime import timedelta

        thirty_days_ago = timezone.now() - timedelta(days=30)
        top_rated_products = _unique_products_from_querysets(
            (
                Product.objects.filter(is_active=True, is_bestseller=True)
                .prefetch_related("images")
                .order_by("-created_at"),
                Product.objects.filter(is_active=True, is_featured=True)
                .prefetch_related("images")
                .order_by("-created_at"),
                Product.objects.filter(is_active=True).prefetch_related("images").order_by("-created_at"),
            ),
            limit,
        )
        new_arrivals = _unique_products_from_querysets(
            (
                Product.objects.filter(is_active=True, created_at__gte=thirty_days_ago)
                .prefetch_related("images")
                .order_by("-created_at"),
                Product.objects.filter(is_active=True).prefetch_related("images").order_by("-created_at"),
            ),
            limit,
        )

    breadcrumb_items = [
        {'name': 'Главная', 'url': None},
    ]

    return render(request, 'shop/index.html', {
        'top_rated_products': top_rated_products,
        'new_arrivals': new_arrivals,
        'breadcrumb_items': breadcrumb_items,
    })

def shop(request):
    """Страница каталога."""
    context = _shop_context(request)
    return render(request, "shop/shop.html", context)


def shop_new_arrivals(request):
    """Новинки — отдельная страница (не дублирует вид полного магазина)."""
    context = _shop_context(request, preset="new_arrivals")
    context.update(
        {
            "page_heading": "Новинки",
            "page_lead": "Подборка из админки: добавляйте позиции в разделе «Новинки: товары».",
            "grid_url": reverse("shop_grid_new_arrivals"),
            "breadcrumb_items": [
                {"name": "Главная", "url": "/"},
                {"name": "Магазин", "url": reverse("shop")},
                {"name": "Новинки", "url": None},
            ],
            "page_title": "Новинки",
            "page_theme": "novinki",
        }
    )
    return render(request, "shop/catalog_section_page.html", context)


def shop_new_arrivals_grid(request):
    context = _shop_context(request, preset="new_arrivals")
    return render(request, "shop/partials/product_grid.html", context)


def shop_promotions(request):
    """Акции — отдельная страница."""
    context = _shop_context(request, preset="promotions")
    context.update(
        {
            "page_heading": "Акции",
            "page_lead": "Специальные цены и выгодные предложения — список задаётся в админке («Акции: товары»).",
            "grid_url": reverse("shop_grid_promotions"),
            "breadcrumb_items": [
                {"name": "Главная", "url": "/"},
                {"name": "Магазин", "url": reverse("shop")},
                {"name": "Акции", "url": None},
            ],
            "page_title": "Акции",
            "page_theme": "akcii",
        }
    )
    return render(request, "shop/catalog_section_page.html", context)


def shop_promotions_grid(request):
    context = _shop_context(request, preset="promotions")
    return render(request, "shop/partials/product_grid.html", context)


def shop_grid(request):
    """HTMX: только сетка товаров (#product-grid)."""
    context = _shop_context(request)
    return render(request, "shop/partials/product_grid.html", context)


def shop_products_api(request):
    """JSON API (совместимость со старым shop.js при необходимости)."""
    if catalog_products_exist():
        qs = filter_catalog_products(request)[:500]
        products_data = []
        for product in qs:
            facade = CatalogProductDisplay(product, user=request.user)
            products_data.append(
                {
                    "id": str(product.pk),
                    "name": product.name,
                    "description": "",
                    "price": str(facade.current_price),
                    "image_url": facade.image_url,
                    "category": product.category.slug if product.category_id else "",
                    "category_display": product.category.name if product.category_id else "",
                    "stock_quantity": product.stock,
                    "stock_status": "В наличии" if product.stock > 0 else "Нет в наличии",
                    "is_active": product.is_active,
                    "is_in_stock": product.stock > 0 and product.is_active,
                    "url": facade.get_absolute_url(),
                }
            )
        return JsonResponse({"products": products_data, "count": len(products_data)})

    products, _, _, _ = _filter_products(request)
    products_data = []
    for product in products:
        products_data.append(
            {
                "id": product.id,
                "name": product.name,
                "description": product.description,
                "price": str(product.current_price),
                "image_url": product.image_url,
                "category": product.category.slug,
                "category_display": product.category.name,
                "stock_quantity": product.stock,
                "stock_status": product.stock_status,
                "is_active": product.is_active,
                "is_in_stock": product.is_in_stock,
                "url": product.get_absolute_url(),
            }
        )
    return JsonResponse({"products": products_data, "count": len(products_data)})


@require_GET
def categories_search_api(request):
    """JSON: дерево корневых категорий с подкатегориями, фильтр по подстроке в названии (q)."""
    q = request.GET.get("q", "")
    roots, allowed_slugs = get_shop_catalog_nav_roots_and_allowed_slugs()
    payload = build_category_nav_payload(roots, allowed_descendant_slugs=allowed_slugs)
    filtered = filter_category_nav(payload, q)
    return JsonResponse({"categories": filtered})


@require_GET
def search_suggest_api(request):
    """Быстрые подсказки товаров для поиска в шапке (desktop/mobile)."""
    query = (request.GET.get("q") or "").strip()
    category_slug = (request.GET.get("category") or "").strip()
    if len(query) < 2:
        return JsonResponse({"items": []})

    items = []
    limit = 8

    if catalog_products_exist():
        qs = CatalogProduct.objects.filter(is_active=True).select_related("category").prefetch_related("images")
        qs = qs.filter(Q(name__icontains=query) | Q(sku__icontains=query))
        if category_slug:
            qs = qs.filter(category__slug=category_slug)
        for product in qs.order_by("name")[:limit]:
            facade = CatalogProductDisplay(product, user=request.user)
            items.append(
                {
                    "name": product.name,
                    "price": str(facade.current_price),
                    "url": facade.get_absolute_url(),
                    "image_url": facade.image_url,
                }
            )
        return JsonResponse({"items": items})

    qs = Product.objects.filter(is_active=True).select_related("category").prefetch_related("images")
    qs = qs.filter(Q(name__icontains=query) | Q(description__icontains=query))
    if category_slug:
        qs = qs.filter(category__slug=category_slug)
    for product in qs.order_by("name")[:limit]:
        items.append(
            {
                "name": product.name,
                "price": str(product.current_price),
                "url": product.get_absolute_url(),
                "image_url": product.image_url,
            }
        )
    return JsonResponse({"items": items})


def pdp(request, slug):
    """Карточка товара."""
    product = get_object_or_404(
        Product.objects.select_related("category").prefetch_related("images"),
        slug=slug,
    )
    related_products = (
        Product.objects.filter(category=product.category, is_active=True)
        .exclude(slug=slug)
        .select_related("category")
        .prefetch_related("images")[:4]
    )

    breadcrumb_items = [
        {"name": "Главная", "url": "/"},
        {"name": "Магазин", "url": "/shop/"},
        {
            "name": product.category.name,
            "url": f"/shop/?categories={product.category.slug}",
        },
        {"name": product.name, "url": None},
    ]

    context = {
        "product": product,
        "related_products": related_products,
        "breadcrumb_items": breadcrumb_items,
    }

    return render(request, "shop/pdp.html", context)


def catalog_pdp(request, product_id):
    """Карточка товара из каталога 1С (products.Product)."""
    product = get_object_or_404(
        CatalogProduct.objects.select_related("category").prefetch_related("images"),
        pk=product_id,
        is_active=True,
    )
    related = (
        CatalogProduct.objects.filter(category_id=product.category_id, is_active=True)
        .exclude(pk=product.pk)
        .prefetch_related("images")
        .order_by("-updated_at")[:4]
    )

    breadcrumb_items = [
        {"name": "Главная", "url": "/"},
        {"name": "Магазин", "url": "/shop/"},
        {
            "name": product.category.name,
            "url": f"/shop/?categories={product.category.slug}",
        },
        {"name": product.name, "url": None},
    ]

    gallery = list(product.gallery_urls)
    if not gallery:
        gallery = [product.image_url]

    catalog_facade = CatalogProductDisplay(product, user=request.user)
    related_facades = [CatalogProductDisplay(p, user=request.user) for p in related]

    return render(
        request,
        "shop/catalog_pdp.html",
        {
            "product": product,
            "catalog_facade": catalog_facade,
            "related_products": related,
            "related_facades": related_facades,
            "breadcrumb_items": breadcrumb_items,
            "pdp_gallery_urls": gallery,
            "pdp_gallery_urls_json": json.dumps(gallery),
        },
    )


def wishlist_login_redirect(request):
    """Неавторизованный клик по «избранному» → сообщение и страница регистрации."""
    messages.info(
        request,
        "Чтобы сохранять товары в избранном, зарегистрируйтесь или войдите в аккаунт.",
    )
    next_url = _sanitize_next_url(request, request.GET.get("next"), "/")
    return redirect(f"{reverse('sign-up')}?{urlencode({'next': next_url})}")


@require_POST
def wishlist_toggle(request):
    """Добавить/убрать товар из избранного (POST, для авторизованных)."""
    if not request.user.is_authenticated:
        next_url = request.POST.get("next") or request.META.get("HTTP_REFERER", "/")
        next_url = _sanitize_next_url(request, next_url, "/")
        url = f"{reverse('sign-up')}?{urlencode({'next': next_url})}"
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {"success": False, "login_required": True, "redirect_url": url},
                status=401,
            )
        messages.info(
            request,
            "Чтобы сохранять товары в избранном, зарегистрируйтесь или войдите в аккаунт.",
        )
        return redirect(url)

    catalog_product_id = (request.POST.get("catalog_product_id") or "").strip()
    product_id_raw = (request.POST.get("product_id") or "").strip()

    if catalog_product_id and product_id_raw:
        err = "Укажите только один тип товара."
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": False, "error": err}, status=400)
        messages.error(request, err)
        return redirect(request.META.get("HTTP_REFERER", reverse("shop")))

    if not catalog_product_id and not product_id_raw:
        err = "Не указан товар."
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": False, "error": err}, status=400)
        messages.error(request, err)
        return redirect(request.META.get("HTTP_REFERER", reverse("shop")))

    if catalog_product_id:
        cp = get_object_or_404(CatalogProduct, pk=catalog_product_id, is_active=True)
        existing = WishlistItem.objects.filter(user=request.user, catalog_product=cp).first()
        if existing:
            existing.delete()
            in_wishlist = False
        else:
            WishlistItem.objects.create(user=request.user, catalog_product=cp)
            in_wishlist = True
    else:
        try:
            pid = int(product_id_raw)
        except (TypeError, ValueError):
            err = "Некорректный товар."
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"success": False, "error": err}, status=400)
            messages.error(request, err)
            return redirect(request.META.get("HTTP_REFERER", reverse("shop")))
        product = get_object_or_404(Product.objects.select_related("category"), pk=pid)
        existing = WishlistItem.objects.filter(user=request.user, shop_product=product).first()
        if existing:
            existing.delete()
            in_wishlist = False
        else:
            WishlistItem.objects.create(user=request.user, shop_product=product)
            in_wishlist = True

    wishlist_count = WishlistItem.objects.filter(user=request.user).count()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse(
            {
                "success": True,
                "in_wishlist": in_wishlist,
                "wishlist_count": wishlist_count,
            }
        )

    messages.success(
        request,
        "Удалено из избранного." if not in_wishlist else "Добавлено в избранное.",
    )
    return _safe_redirect_same_site(request)


def wishlist(request):
    """Страница избранного в личном кабинете."""
    if not request.user.is_authenticated:
        messages.info(
            request,
            "Чтобы видеть избранное, зарегистрируйтесь или войдите в аккаунт.",
        )
        return redirect(f"{reverse('sign-up')}?{urlencode({'next': request.get_full_path()})}")

    qs = (
        WishlistItem.objects.filter(user=request.user)
        .select_related("shop_product", "shop_product__category", "catalog_product", "catalog_product__category")
        .prefetch_related("catalog_product__images", "shop_product__images")
        .order_by("-created_at")
    )

    paginator = Paginator(qs, 12)
    page_number = _parse_positive_int_bounded(
        request.GET.get("page"),
        default=1,
        min_value=1,
        max_value=MAX_PAGINATION_PAGE,
    )
    page_obj = paginator.get_page(page_number)

    wishlist_rows = []
    for wi in page_obj:
        if wi.catalog_product_id:
            wishlist_rows.append(
                {
                    "catalog": True,
                    "product": CatalogProductDisplay(wi.catalog_product, user=request.user),
                }
            )
        else:
            wishlist_rows.append({"catalog": False, "product": wi.shop_product})

    breadcrumb_items = [
        {"name": "Главная", "url": "/"},
        {"name": "Личный кабинет", "url": reverse("profile")},
        {"name": "Избранное", "url": None},
    ]
    user_profile = None
    try:
        user_profile = request.user.profile
    except Exception:
        user_profile = None

    return render(
        request,
        "shop/wishlist.html",
        {
            "wishlist_rows": wishlist_rows,
            "wishlist_page": page_obj,
            "breadcrumb_items": breadcrumb_items,
            "page_title": "Избранное",
            "user_profile": user_profile,
            "wishlist_count": qs.count(),
            "active_tab": "wishlist",
        },
    )


def sign_in(request):

    # Redirect authenticated users to the home page
    if request.user.is_authenticated:
        return redirect('landing')

    # Breadcrumb for sign-in page
    breadcrumb_items = [
        {'name': 'Главная', 'url': '/'},
        {'name': 'Вход', 'url': None}
    ]
    
    context = {
        'breadcrumb_items': breadcrumb_items,
    }
    
    return render(request, 'shop/sign-in.html', context)

def sign_up(request):

    # Redirect authenticated users to the home page
    if request.user.is_authenticated:
        return redirect('landing')
    
    # Breadcrumb for sign-up page
    breadcrumb_items = [
        {'name': 'Главная', 'url': '/'},
        {'name': 'Регистрация', 'url': None}
    ]
    
    pow_token, pow_question = _issue_pow_challenge("signup")
    context = {
        'breadcrumb_items': breadcrumb_items,
        "pow_token": pow_token,
        "pow_question": pow_question,
    }
    
    return render(request, 'shop/sign-up.html', context)

def cart_count_api(request):
    """API endpoint to get current cart count"""
    cart = _get_or_create_cart(request)
    items = cart.items.all() if cart else []
    # Return number of distinct items (CartItem rows), not the sum of quantities
    cart_item_count = items.count() if hasattr(items, 'count') else len(items)
    
    return JsonResponse({'count': cart_item_count})


def about_us(request):
    """About Us page rendering a prototype-style layout"""
    breadcrumb_items = [
        {'name': 'Главная', 'url': '/'},
        {'name': 'О нас', 'url': None}
    ]

    context = {
        'breadcrumb_items': breadcrumb_items,
    }

    return render(request, 'shop/about-us.html', context)


def contact_us(request):
    """Contact Us page with feedback form (same backend as /feedback/)."""
    breadcrumb_items = [
        {'name': 'Главная', 'url': '/'},
        {'name': 'Контакты', 'url': None},
    ]

    if request.method == 'POST':
        try:
            name = request.POST.get('name', '').strip()
            email = request.POST.get('email', '').strip()
            category = request.POST.get('category', 'general')
            subject = request.POST.get('subject', '').strip()
            message_text = request.POST.get('message', '').strip()
            pow_token = (request.POST.get("pow_token") or "").strip()
            pow_answer = (request.POST.get("pow_answer") or "").strip()

            if not all([name, email, subject, message_text]):
                messages.error(request, 'Заполните все обязательные поля.')
                return redirect('contact-us')
            try:
                validate_email(email)
            except ValidationError:
                messages.error(request, "Укажите корректный email.")
                return redirect("contact-us")
            allowed_categories = {c[0] for c in Feedback.CATEGORY_CHOICES}
            if category not in allowed_categories:
                messages.error(request, "Некорректная категория сообщения.")
                return redirect("contact-us")
            if not _verify_pow_challenge("contact", pow_token, pow_answer):
                messages.error(request, "Проверка anti-bot не пройдена. Обновите страницу и попробуйте снова.")
                return redirect("contact-us")

            Feedback.objects.create(
                user=request.user if request.user.is_authenticated else None,
                name=name,
                email=email,
                category=category,
                subject=subject,
                message=message_text,
            )
            notify_feedback_created(
                name=name,
                email=email,
                category=category,
                subject=subject,
                message=message_text,
            )

            messages.success(
                request,
                'Спасибо за обратную связь! Мы рассмотрим её в ближайшее время.',
            )
            return redirect('contact-us')

        except Exception as e:
            messages.error(request, f'Ошибка при отправке: {str(e)}')
            return redirect('contact-us')

    category_choices = Feedback.CATEGORY_CHOICES
    initial_data = {}
    if request.user.is_authenticated:
        initial_data['name'] = (
            f'{request.user.first_name} {request.user.last_name}'.strip()
            or request.user.email
        )
        initial_data['email'] = request.user.email

    contact_pow_token, contact_pow_question = _issue_pow_challenge("contact")
    context = {
        'breadcrumb_items': breadcrumb_items,
        'category_choices': category_choices,
        'initial_data': initial_data,
        "pow_token": contact_pow_token,
        "pow_question": contact_pow_question,
    }

    return render(request, 'shop/contact-us.html', context)


def _safe_redirect_same_site(request, *, fallback_name="shop"):
    """После POST «в корзину» без AJAX — вернуть на предыдущую страницу (каталог), не на /cart/."""
    referer = request.META.get("HTTP_REFERER")
    if referer and url_has_allowed_host_and_scheme(
        referer,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(referer)
    return redirect(fallback_name)


def _get_or_create_cart(request):
    """Return an active Cart for the current user or session."""
    session_key = request.session.session_key
    if not session_key:
        request.session.create()
        session_key = request.session.session_key

    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user, is_active=True, defaults={'session_key': session_key})
        # If there is an anonymous cart for this session, merge it
        try:
            anon_cart = Cart.objects.get(session_key=session_key, user__isnull=True, is_active=True)
            if anon_cart.pk != cart.pk:
                with transaction.atomic():
                    for item in anon_cart.items.select_related("product", "catalog_product").all():
                        if item.catalog_product_id:
                            ci, created = CartItem.objects.get_or_create(
                                cart=cart,
                                catalog_product=item.catalog_product,
                                defaults={
                                    "quantity": item.quantity,
                                    "price": item.price,
                                    "product": None,
                                    "special_instructions": item.special_instructions,
                                },
                            )
                        else:
                            ci, created = CartItem.objects.get_or_create(
                                cart=cart,
                                product=item.product,
                                defaults={
                                    "quantity": item.quantity,
                                    "price": item.price,
                                    "special_instructions": item.special_instructions,
                                },
                            )
                        if not created:
                            ci.quantity += item.quantity
                            if not ci.special_instructions and item.special_instructions:
                                ci.special_instructions = item.special_instructions
                                ci.save(
                                    update_fields=[
                                        "quantity",
                                        "special_instructions",
                                        "updated_at",
                                    ]
                                )
                            else:
                                ci.save(update_fields=["quantity", "updated_at"])
                    anon_cart.is_active = False
                    anon_cart.save()
        except Cart.DoesNotExist:
            pass
    else:
        cart, created = Cart.objects.get_or_create(session_key=session_key, user=None, is_active=True)
    return cart

@require_POST
def add_to_cart(request):
    """Add product to cart or increment quantity (shop.Product или каталог 1С)."""
    catalog_product_id = (request.POST.get("catalog_product_id") or "").strip()
    product_id = request.POST.get("product_id")
    qty = _parse_positive_int_bounded(
        request.POST.get("quantity", 1),
        default=1,
        min_value=1,
        max_value=MAX_CART_ITEM_QTY,
    )
    special_instructions = _sanitize_special_instructions(
        request.POST.get("special_instructions")
    )

    if qty < 1:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": False, "error": "Некорректное количество"}, status=400)
        messages.error(request, "Некорректное количество")
        return redirect(request.META.get("HTTP_REFERER", "shop"))

    cart = _get_or_create_cart(request)

    if catalog_product_id:
        with transaction.atomic():
            cp = get_object_or_404(
                CatalogProduct.objects.select_for_update(),
                pk=catalog_product_id,
                is_active=True,
            )
            line_price = catalog_unit_price(cp, request.user)
            existing_item = CartItem.objects.filter(cart=cart, catalog_product=cp).first()
            new_quantity = (existing_item.quantity if existing_item else 0) + qty
            if new_quantity > cp.stock:
                err = f"Недостаточно на складе. В наличии: {cp.stock}."
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse({"success": False, "error": err}, status=400)
                messages.error(request, err)
                return redirect(request.META.get("HTTP_REFERER", "shop"))
            item, created = CartItem.objects.get_or_create(
                cart=cart,
                catalog_product=cp,
                defaults={
                    "quantity": qty,
                    "price": line_price,
                    "product": None,
                    "special_instructions": special_instructions,
                },
            )
            if not created:
                item.quantity += qty
                update_fields = ["quantity", "updated_at"]
                if special_instructions:
                    item.special_instructions = special_instructions
                    update_fields.insert(1, "special_instructions")
                item.save(update_fields=update_fields)
        product_name = cp.name
    else:
        if not product_id:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"success": False, "error": "Не указан товар"}, status=400)
            messages.error(request, "Не указан товар")
            return redirect(request.META.get("HTTP_REFERER", "shop"))
        with transaction.atomic():
            product = get_object_or_404(Product.objects.select_for_update(), pk=product_id)
            existing_item = CartItem.objects.filter(cart=cart, product=product).first()
            new_quantity = (existing_item.quantity if existing_item else 0) + qty

            if new_quantity > product.stock:
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse(
                        {
                            "success": False,
                            "error": f"Недостаточно на складе. В наличии: {product.stock}.",
                        },
                        status=400,
                    )
                messages.error(
                    request,
                    f"Недостаточно на складе. В наличии: {product.stock}.",
                )
                return redirect(request.META.get("HTTP_REFERER", "shop"))

            item, created = CartItem.objects.get_or_create(
                cart=cart,
                product=product,
                defaults={
                    "quantity": qty,
                    "price": product.current_price,
                    "special_instructions": special_instructions,
                },
            )
            if not created:
                item.quantity += qty
                update_fields = ["quantity", "updated_at"]
                if special_instructions:
                    item.special_instructions = special_instructions
                    update_fields.insert(1, "special_instructions")
                item.save(update_fields=update_fields)
        product_name = product.name

    cart_item_count = cart.items.count()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse(
            {
                "success": True,
                "message": f"{product_name} добавлен в корзину",
                "cart_count": cart_item_count,
                "product_name": product_name,
                "quantity_added": qty,
                "special_instructions": special_instructions,
            }
        )

    messages.success(request, f"«{product_name}» добавлен в корзину!")
    return _safe_redirect_same_site(request)

# Replace the simple cart view above with this one so /cart/ shows items
def cart(request):
    breadcrumb_items = [
        {'name': 'Главная', 'url': '/'},
        {'name': 'Корзина', 'url': None}
    ]
    cart_obj = _get_or_create_cart(request)
    items = (
        cart_obj.items.select_related("product", "catalog_product").all() if cart_obj else []
    )
    summary = _cart_summary_payload(cart_obj)
    shipping_preview = Decimal(summary["shipping_fee"])
    context = {
        "breadcrumb_items": breadcrumb_items,
        "cart": cart_obj,
        "items": items,
        "shipping_fee": shipping_preview,
        "cart_summary": summary,
    }
    return render(request, "shop/cart.html", context)

@require_POST
def update_cart_item(request, item_id):
    """Update quantity for a given cart item (set or remove if 0)."""
    cart = _get_or_create_cart(request)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    item = get_object_or_404(
        CartItem.objects.select_related("product", "catalog_product"),
        pk=item_id,
    )
    if item.cart_id != cart.id:
        if is_ajax:
            return JsonResponse({"success": False, "error": "Неверная корзина"}, status=403)
        return redirect("cart")
    qty = _parse_positive_int_bounded(
        request.POST.get("quantity", item.quantity),
        default=item.quantity,
        min_value=0,
        max_value=MAX_CART_ITEM_QTY,
    )
    special_instructions = _sanitize_special_instructions(
        request.POST.get("special_instructions")
    )
    if qty <= 0:
        item.delete()
        cart = _get_or_create_cart(request)
        if is_ajax:
            return JsonResponse({"success": True, **_cart_summary_payload(cart)})
        return redirect("cart")

    with transaction.atomic():
        locked = CartItem.objects.select_for_update().get(pk=item.pk)
        if locked.cart_id != cart.id:
            if is_ajax:
                return JsonResponse({"success": False, "error": "Неверная корзина"}, status=403)
            return redirect("cart")
        if locked.catalog_product_id:
            cp = CatalogProduct.objects.select_for_update().get(pk=locked.catalog_product_id)
            if qty > cp.stock:
                msg = f"Недостаточно товара «{cp.name}». В наличии: {cp.stock}."
                if is_ajax:
                    return JsonResponse({"success": False, "error": msg}, status=400)
                messages.error(request, msg)
                return redirect("cart")
        else:
            product = Product.objects.select_for_update().get(pk=locked.product_id)
            if qty > product.stock:
                msg = f"Недостаточно товара «{product.name}». В наличии: {product.stock}."
                if is_ajax:
                    return JsonResponse({"success": False, "error": msg}, status=400)
                messages.error(request, msg)
                return redirect("cart")
        locked.quantity = qty
        locked.special_instructions = special_instructions
        locked.save(update_fields=["quantity", "special_instructions", "updated_at"])
    cart = _get_or_create_cart(request)
    if is_ajax:
        return JsonResponse({"success": True, **_cart_summary_payload(cart)})
    return redirect("cart")

@require_POST
def remove_cart_item(request, item_id):
    item = get_object_or_404(CartItem, pk=item_id)
    cart = _get_or_create_cart(request)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if item.cart_id != cart.id:
        if is_ajax:
            return JsonResponse({"success": False, "error": "Неверная корзина"}, status=403)
        return redirect("cart")
    item.delete()
    cart = _get_or_create_cart(request)
    if is_ajax:
        return JsonResponse({"success": True, **_cart_summary_payload(cart)})
    return redirect("cart")


def checkout(request):
    from .services.html_catalog_order import place_order_from_catalog_cart_items

    cart = _get_or_create_cart(request)
    saved_addresses = []
    if request.user.is_authenticated:
        saved_addresses = list(
            Address.objects.filter(user=request.user).order_by("-is_default", "-created_at")
        )

    if request.method == "POST" and "selected_items" in request.POST:
        selected_item_ids = request.POST.getlist("selected_items")
        if selected_item_ids:
            request.session["selected_items"] = selected_item_ids
        else:
            messages.warning(request, "Выберите хотя бы один товар для оформления заказа.")
            return redirect("cart")
    else:
        selected_item_ids = request.session.get("selected_items", [])

    if not selected_item_ids:
        messages.warning(request, "Выберите хотя бы один товар для оформления заказа.")
        return redirect("cart")

    items = (
        cart.items.select_related("product", "catalog_product").filter(id__in=selected_item_ids)
        if cart
        else []
    )

    if not items:
        messages.warning(request, "Выбранные товары больше недоступны в корзине.")
        if "selected_items" in request.session:
            del request.session["selected_items"]
        return redirect("cart")

    has_catalog = any(i.catalog_product_id for i in items)
    has_shop = any(i.product_id for i in items)
    if has_catalog and has_shop:
        messages.error(
            request,
            "Нельзя оформить в одном заказе товары каталога 1С и демо-товары. Уберите лишнее из корзины.",
        )
        return redirect("cart")

    for item in items:
        if item.catalog_product_id:
            available = item.catalog_product.stock
            product_name = item.catalog_product.name
        else:
            available = item.product.stock
            product_name = item.product.name
        if item.quantity > available:
            messages.error(
                request,
                f"Недостаточно товара «{product_name}». В наличии: {available} шт. Обновите количество в корзине.",
            )
            return redirect("cart")

    subtotal = Decimal("0.00")
    for item in items:
        if item.catalog_product_id:
            subtotal += item.price * item.quantity
        else:
            subtotal += item.product.current_price * item.quantity

    delivery_method = "pickup"
    if request.method == "POST" and "full_name" in request.POST:
        delivery_method = (request.POST.get("delivery_method") or "pickup").strip().lower()
    elif request.method == "GET":
        delivery_method = (request.GET.get("delivery_method") or "pickup").strip().lower()

    if delivery_method not in {"pickup", "courier"}:
        delivery_method = "pickup"

    shipping_fee = _shipping_fee_for_delivery_method(delivery_method, subtotal)

    grand_total = subtotal + shipping_fee

    if has_catalog and not request.user.is_authenticated:
        messages.info(request, "Войдите в аккаунт, чтобы оформить заказ каталога 1С.")
        return redirect(f"{reverse('sign-in')}?next={reverse('checkout')}")

    def _checkout_error_response(
        msg: str,
        full_name: str,
        email: str,
        phone: str,
        address: str,
        method: str,
        order_comment: str,
        address_source: str,
        saved_address_id: str,
    ):
        breadcrumb_items = [
            {"name": "Главная", "url": "/"},
            {"name": "Корзина", "url": "/cart"},
            {"name": "Оформление заказа", "url": None},
        ]
        messages.error(request, msg)
        return render(
            request,
            "shop/checkout.html",
            {
                "cart": cart,
                "items": items,
                "subtotal": subtotal,
                "shipping_fee": shipping_fee,
                "grand_total": grand_total,
                "saved_addresses": saved_addresses,
                "breadcrumb_items": breadcrumb_items,
                "checkout_form": {
                    "full_name": full_name,
                    "email": email,
                    "phone": phone,
                    "address": address,
                    "delivery_method": method,
                    "order_comment": order_comment,
                    "address_source": address_source,
                    "saved_address_id": saved_address_id,
                },
            },
        )

    def _stock_error_message(code: str) -> str:
        raw_id = code.split(":", 1)[1] if ":" in code else ""
        for line in items:
            if line.catalog_product_id and str(line.catalog_product_id) == raw_id:
                return (
                    f"Недостаточно товара «{line.catalog_product.name}». "
                    f"В наличии: {line.catalog_product.stock} шт. Обновите количество в корзине."
                )
            if line.product_id and str(line.product_id) == raw_id:
                return (
                    f"Недостаточно товара «{line.product.name}». "
                    f"В наличии: {line.product.stock} шт. Обновите количество в корзине."
                )
        return "Не удалось зарезервировать товар. Обновите корзину и попробуйте снова."

    if request.method == "POST" and "full_name" in request.POST:
        full_name = request.POST.get("full_name", "").strip()
        email = request.POST.get("email", "").strip()
        phone = request.POST.get("phone", "").strip()
        address = request.POST.get("address", "").strip()
        order_comment = request.POST.get("order_comment", "").strip()
        address_source = (request.POST.get("address_source") or "new").strip().lower()
        saved_address_id = (request.POST.get("saved_address_id") or "").strip()
        payment_method = request.POST.get("payment_method", "COD")
        delivery_method = (request.POST.get("delivery_method") or "pickup").strip().lower()
        if delivery_method not in {"pickup", "courier"}:
            delivery_method = "pickup"
        shipping_fee = _shipping_fee_for_delivery_method(delivery_method, subtotal)
        grand_total = subtotal + shipping_fee

        if address_source not in {"saved", "new"}:
            address_source = "new"
        if address_source == "saved" and request.user.is_authenticated and saved_address_id:
            selected_address = Address.objects.filter(
                id=saved_address_id,
                user=request.user,
            ).first()
            if selected_address:
                address = selected_address.full_address
            else:
                return _checkout_error_response(
                    "Выберите корректный сохранённый адрес или введите новый.",
                    full_name,
                    email,
                    phone,
                    address,
                    delivery_method,
                    order_comment,
                    address_source,
                    saved_address_id,
                )

        if delivery_method == "pickup":
            if not address:
                address = "Самовывоз"
        elif not address:
            messages.error(request, "Укажите адрес доставки для курьерской доставки.")
            breadcrumb_items = [
                {"name": "Главная", "url": "/"},
                {"name": "Корзина", "url": "/cart"},
                {"name": "Оформление заказа", "url": None},
            ]
            return render(
                request,
                "shop/checkout.html",
                {
                    "cart": cart,
                    "items": items,
                    "subtotal": subtotal,
                    "shipping_fee": shipping_fee,
                    "grand_total": grand_total,
                    "saved_addresses": saved_addresses,
                    "delivery_method": delivery_method,
                    "breadcrumb_items": breadcrumb_items,
                    "checkout_form": {
                        "full_name": full_name,
                        "email": email,
                        "phone": phone,
                        "address": address,
                        "delivery_method": delivery_method,
                        "order_comment": order_comment,
                        "address_source": address_source,
                        "saved_address_id": saved_address_id,
                    },
                },
            )

        if not all([full_name, email, phone, address, payment_method]):
            messages.error(request, "Заполните все обязательные поля.")
            breadcrumb_items = [
                {"name": "Главная", "url": "/"},
                {"name": "Корзина", "url": "/cart"},
                {"name": "Оформление заказа", "url": None},
            ]
            return render(
                request,
                "shop/checkout.html",
                {
                    "cart": cart,
                    "items": items,
                    "subtotal": subtotal,
                    "shipping_fee": shipping_fee,
                    "grand_total": grand_total,
                    "saved_addresses": saved_addresses,
                    "breadcrumb_items": breadcrumb_items,
                    "checkout_form": {
                        "full_name": full_name,
                        "email": email,
                        "phone": phone,
                        "address": address,
                        "delivery_method": delivery_method,
                        "order_comment": order_comment,
                        "address_source": address_source,
                        "saved_address_id": saved_address_id,
                    },
                },
            )

        total_amount = subtotal + shipping_fee

        if has_catalog:
            try:
                integration_order = place_order_from_catalog_cart_items(
                    user=request.user,
                    cart_items=list(items),
                    full_name=full_name,
                    email=email,
                    phone=phone,
                    address=address,
                    payment_method=payment_method,
                    delivery_method=delivery_method,
                    order_comment=order_comment,
                    subtotal=subtotal,
                    shipping_fee=shipping_fee,
                )
            except ValueError as exc:
                code = str(exc)
                if code == "no_external_id":
                    return _checkout_error_response(
                        "Контрагент 1С не привязан к профилю. Дождитесь синхронизации клиентов или обратитесь в поддержку.",
                        full_name,
                        email,
                        phone,
                        address,
                        delivery_method,
                        order_comment,
                        address_source,
                        saved_address_id,
                    )
                if code.startswith("stock:"):
                    return _checkout_error_response(
                        _stock_error_message(code),
                        full_name,
                        email,
                        phone,
                        address,
                        delivery_method,
                        order_comment,
                        address_source,
                        saved_address_id,
                    )
                if code == "Требуется вход":
                    return redirect(f"{reverse('sign-in')}?next={reverse('checkout')}")
                return _checkout_error_response(
                    code,
                    full_name,
                    email,
                    phone,
                    address,
                    delivery_method,
                    order_comment,
                    address_source,
                    saved_address_id,
                )

            for item in items:
                item.delete()
            if "selected_items" in request.session:
                del request.session["selected_items"]
            recent = request.session.get("recent_order_ids", [])
            recent = [str(integration_order.id)] + [x for x in recent if x != str(integration_order.id)]
            request.session["recent_order_ids"] = recent[:20]

            breadcrumb_items = [
                {"name": "Главная", "url": "/"},
                {"name": "Корзина", "url": "/cart"},
                {"name": "Оформление заказа", "url": "/checkout"},
                {"name": "Заказ оформлен", "url": None},
            ]
            messages.success(
                request,
                f"Заказ принят. Номер на сайте: {integration_order.id}",
            )
            notify_order_created(integration_order)
            return render(
                request,
                "shop/checkout_success_catalog.html",
                {
                    "integration_order": integration_order,
                    "delivery_address": address,
                    "delivery_method": delivery_method,
                    "breadcrumb_items": breadcrumb_items,
                },
            )

        from .services.demo_order import place_demo_order_from_cart_items

        try:
            order = place_demo_order_from_cart_items(
                user=request.user if request.user.is_authenticated else None,
                cart_items=list(items),
                full_name=full_name,
                email=email,
                    phone=phone,
                address=address,
                payment_method=payment_method,
                delivery_method=delivery_method,
                    order_comment=order_comment,
                subtotal=subtotal,
                shipping_fee=shipping_fee,
            )
        except ValueError as exc:
            code = str(exc)
            if code.startswith("stock:"):
                return _checkout_error_response(
                    _stock_error_message(code),
                    full_name,
                    email,
                    phone,
                    address,
                    delivery_method,
                    order_comment,
                    address_source,
                    saved_address_id,
                )
            return _checkout_error_response(
                code,
                full_name,
                email,
                phone,
                address,
                delivery_method,
                order_comment,
                address_source,
                saved_address_id,
            )

        for item in items:
            item.delete()
        if "selected_items" in request.session:
            del request.session["selected_items"]
        recent = request.session.get("recent_order_ids", [])
        recent = [str(order.id)] + [x for x in recent if x != str(order.id)]
        request.session["recent_order_ids"] = recent[:20]

        attach_line_display_products(order)

        breadcrumb_items = [
            {"name": "Главная", "url": "/"},
            {"name": "Корзина", "url": "/cart"},
            {"name": "Оформление заказа", "url": "/checkout"},
            {"name": "Заказ оформлен", "url": None},
        ]

        messages.success(request, f"Заказ №{order.id} успешно оформлен!")
        notify_order_created(order)
        return render(
            request,
            "shop/checkout_success.html",
            {
                "order": order,
                "breadcrumb_items": breadcrumb_items,
            },
        )

    breadcrumb_items = [
        {"name": "Главная", "url": "/"},
        {"name": "Корзина", "url": "/cart"},
        {"name": "Оформление заказа", "url": None},
    ]

    return render(
        request,
        "shop/checkout.html",
        {
            "cart": cart,
            "items": items,
            "subtotal": subtotal,
            "shipping_fee": shipping_fee,
            "grand_total": grand_total,
            "saved_addresses": saved_addresses,
            "delivery_method": delivery_method,
            "breadcrumb_items": breadcrumb_items,
        },
    )
@login_required
def user_profile(request):  # Renamed from 'profile' to 'user_profile'
    """User profile page"""
    from users.models import WholesaleUpgradeRequest

    breadcrumb_items = [
        {'name': 'Главная', 'url': '/'},
        {'name': 'Профиль', 'url': None}
    ]

    if request.method == "POST" and "request_wholesale" in request.POST:
        if getattr(request.user, "user_type", "retail") != "retail":
            messages.warning(request, "Заявка на опт доступна только для розничного аккаунта.")
        elif WholesaleUpgradeRequest.objects.filter(
            user=request.user,
            status=WholesaleUpgradeRequest.Status.PENDING,
        ).exists():
            messages.info(request, "Заявка уже на рассмотрении.")
        else:
            WholesaleUpgradeRequest.objects.create(
                user=request.user,
                comment=(request.POST.get("wholesale_comment") or "").strip()[:2000],
            )
            notify_wholesale_request_created(
                email=request.user.email,
                comment=(request.POST.get("wholesale_comment") or "").strip()[:2000],
            )
            messages.success(request, "Заявка на оптовый доступ отправлена менеджеру.")
        return redirect("profile")

    user_profile = None
    if request.user.is_authenticated:
        try:
            user_profile = request.user.profile
        except Exception:
            user_profile = None

        # Handle POST for editing profile information including profile picture
        if request.method == 'POST' and user_profile:
            # Handle profile picture upload
            if 'profile_picture' in request.FILES:
                try:
                    _validate_profile_picture_upload(request.FILES["profile_picture"])
                except SuspiciousOperation as exc:
                    messages.error(request, str(exc))
                    return redirect("profile")
                # Delete old profile picture if it exists
                if user_profile.profile_picture:
                    try:
                        user_profile.profile_picture.delete(save=False)
                    except Exception:
                        pass  # Ignore errors if file doesn't exist
                
                user_profile.profile_picture = request.FILES['profile_picture']
            
            # Handle personal information updates
            if 'update_personal_info' in request.POST:
                # Update User model fields
                first_name = request.POST.get('first_name', '').strip()
                last_name = request.POST.get('last_name', '').strip()
                email = request.POST.get('email', '').strip()
                
                if first_name:
                    request.user.first_name = first_name
                if last_name:
                    request.user.last_name = last_name
                if email:
                    request.user.email = email
                
                request.user.save()
                
                # Update UserProfile fields
                contact_number = request.POST.get('contact_number', '').strip()
                if contact_number:
                    user_profile.contact_number = contact_number
            
            # Handle settings updates
            if 'update_settings' in request.POST:
                preferred_currency = request.POST.get('preferred_currency', '')
                preferred_payment_method = request.POST.get('preferred_payment_method', '')
                
                if preferred_currency:
                    user_profile.preferred_currency = preferred_currency
                if preferred_payment_method:
                    user_profile.preferred_payment_method = preferred_payment_method
            
            # Handle address updates (legacy support)
            address = request.POST.get('house_address', '').strip()
            if address:
                user_profile.house_address = address
            
            user_profile.save()
    
    # Get user addresses
    user_addresses = []
    if request.user.is_authenticated:
        user_addresses = Address.objects.filter(user=request.user).order_by('-is_default', '-created_at')

    wholesale_pending = None
    if (
        request.user.is_authenticated
        and getattr(request.user, "user_type", "retail") == "retail"
        and not can_access_manager_panel(request.user)
    ):
        wholesale_pending = WholesaleUpgradeRequest.objects.filter(
            user=request.user,
            status=WholesaleUpgradeRequest.Status.PENDING,
        ).first()

    wishlist_count = 0
    if request.user.is_authenticated:
        wishlist_count = WishlistItem.objects.filter(user=request.user).count()

    context = {
        'breadcrumb_items': breadcrumb_items,
        'user': request.user,
        'user_profile': user_profile,
        'user_addresses': user_addresses,
        'wholesale_pending': wholesale_pending,
        'is_manager': can_access_manager_panel(request.user),
        'wishlist_count': wishlist_count,
    }

    return render(request, 'shop/profile.html', context)


def add_address(request):
    """Add a new address"""
    if not request.user.is_authenticated:
        return redirect('sign-in')
    
    if request.method == 'POST':
        try:
            # Get form data
            label = request.POST.get('label', '').strip()
            address_type = request.POST.get('address_type', 'home')
            street_address = request.POST.get('street_address', '').strip()
            city = request.POST.get('city', '').strip()
            state_province = request.POST.get('state_province', '').strip()
            postal_code = request.POST.get('postal_code', '').strip()
            country = request.POST.get('country', 'Kyrgyzstan').strip()
            is_default = request.POST.get('is_default') == 'on'
            
            # Validate required fields
            if not all([label, street_address, city, state_province, postal_code]):
                messages.error(request, 'Заполните все обязательные поля.')
                return redirect('profile')
            
            # Create new address
            Address.objects.create(
                user=request.user,
                label=label,
                address_type=address_type,
                street_address=street_address,
                city=city,
                state_province=state_province,
                postal_code=postal_code,
                country=country,
                is_default=is_default
            )
            
            messages.success(request, 'Адрес успешно добавлен!')
            
        except Exception as e:
            messages.error(request, f'Ошибка при добавлении адреса: {str(e)}')
    
    return redirect('profile')

def edit_address(request, address_id):
    """Edit an existing address"""
    if not request.user.is_authenticated:
        return redirect('sign-in')
    
    address = get_object_or_404(Address, id=address_id, user=request.user)
    
    if request.method == 'POST':
        try:
            # Update address fields
            address.label = request.POST.get('label', '').strip()
            address.address_type = request.POST.get('address_type', 'home')
            address.street_address = request.POST.get('street_address', '').strip()
            address.city = request.POST.get('city', '').strip()
            address.state_province = request.POST.get('state_province', '').strip()
            address.postal_code = request.POST.get('postal_code', '').strip()
            address.country = request.POST.get('country', 'Kyrgyzstan').strip()
            address.is_default = request.POST.get('is_default') == 'on'
            
            # Validate required fields
            if not all([address.label, address.street_address, address.city, address.state_province, address.postal_code]):
                messages.error(request, 'Заполните все обязательные поля.')
                return redirect('profile')
            
            address.save()
            messages.success(request, 'Адрес успешно обновлён!')
            
        except Exception as e:
            messages.error(request, f'Ошибка при обновлении адреса: {str(e)}')
    
    return redirect('profile')

def delete_address(request, address_id):
    """Delete an address"""
    if not request.user.is_authenticated:
        return redirect('sign-in')
    
    address = get_object_or_404(Address, id=address_id, user=request.user)
    
    if request.method == 'POST':
        try:
            address.delete()
            messages.success(request, 'Адрес успешно удалён!')
        except Exception as e:
            messages.error(request, f'Ошибка при удалении адреса: {str(e)}')
    
    return redirect('profile')

def change_password(request):
    """Change user password"""
    if not request.user.is_authenticated:
        return redirect('sign-in')
    
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        # Validate current password
        if not request.user.check_password(current_password):
            messages.error(request, 'Неверный текущий пароль.')
            return redirect('profile')
        
        # Validate new password
        if new_password != confirm_password:
            messages.error(request, 'Пароли не совпадают.')
            return redirect('profile')
        
        if len(new_password) < 8:
            messages.error(request, 'Пароль должен быть не менее 8 символов.')
            return redirect('profile')
        
        try:
            # Change password
            request.user.set_password(new_password)
            request.user.save()
            
            # Update session to prevent logout
            update_session_auth_hash(request, request.user)
            
            messages.success(request, 'Пароль успешно изменён!')
        except Exception as e:
            messages.error(request, f'Ошибка при смене пароля: {str(e)}')
    
    return redirect('profile')

def delete_account(request):
    """Delete user account with confirmation"""
    if not request.user.is_authenticated:
        return redirect('sign-in')
    
    if request.method == 'POST':
        password_confirmation = request.POST.get('password_confirmation')
        
        # Verify password
        if not request.user.check_password(password_confirmation):
            messages.error(request, 'Неверный пароль. Удаление аккаунта отменено.')
            return redirect('profile')
        
        try:
            # Delete user's related data first
            user = request.user
            
            # Delete user's addresses
            Address.objects.filter(user=user).delete()
            
            # Delete user profile if exists
            try:
                if hasattr(user, "profile"):
                    user.profile.delete()
            except UserProfile.DoesNotExist:
                pass
            
            email = user.email

            # Delete the user account
            user.delete()

            # Clear session
            request.session.flush()

            messages.success(request, f'Аккаунт {email} удалён. Будем рады видеть вас снова!')
            return redirect('landing')
            
        except Exception as e:
            messages.error(request, f'Ошибка при удалении аккаунта: {str(e)}')
            return redirect('profile')
    
    return redirect('profile')

def feedback(request):
    """Feedback page with submission form and user's feedback history"""

    breadcrumb_items = [
        {'name': 'Главная', 'url': '/'},
        {'name': 'Обратная связь', 'url': None}
    ]
    
    if request.method == 'POST':
        try:
            # Get form data
            name = request.POST.get('name', '').strip()
            email = request.POST.get('email', '').strip()
            category = request.POST.get('category', 'general')
            subject = request.POST.get('subject', '').strip()
            message_text = request.POST.get('message', '').strip()
            
            # Validate required fields
            if not all([name, email, subject, message_text]):
                messages.error(request, 'Заполните все обязательные поля.')
                return redirect('feedback')
            try:
                validate_email(email)
            except ValidationError:
                messages.error(request, "Укажите корректный email.")
                return redirect("feedback")
            allowed_categories = {c[0] for c in Feedback.CATEGORY_CHOICES}
            if category not in allowed_categories:
                messages.error(request, "Некорректная категория сообщения.")
                return redirect("feedback")
            
            # Create feedback
            feedback_obj = Feedback.objects.create(
                user=request.user if request.user.is_authenticated else None,
                name=name,
                email=email,
                category=category,
                subject=subject,
                message=message_text
            )
            notify_feedback_created(
                name=name,
                email=email,
                category=category,
                subject=subject,
                message=message_text,
            )
            
            messages.success(request, 'Спасибо за обратную связь! Мы рассмотрим её в ближайшее время.')
            return redirect('feedback')
            
        except Exception as e:
            messages.error(request, f'Ошибка при отправке: {str(e)}')
            return redirect('feedback')
    
    # Get category choices for the form
    category_choices = Feedback.CATEGORY_CHOICES
    
    # Pre-fill user data if authenticated
    initial_data = {}
    if request.user.is_authenticated:
        initial_data['name'] = f"{request.user.first_name} {request.user.last_name}".strip() or request.user.email
        initial_data['email'] = request.user.email
    
    # Get user's feedback history if authenticated
    user_feedbacks = []
    if request.user.is_authenticated:
        user_feedbacks = Feedback.objects.filter(user=request.user).order_by('-created_at')
    
    context = {
        'breadcrumb_items': breadcrumb_items,
        'category_choices': category_choices,
        'initial_data': initial_data,
        'user_feedbacks': user_feedbacks,
    }
    
    return render(request, 'shop/feedback.html', context)

def feedback_success(request):
    """Feedback success page"""
    breadcrumb_items = [
        {'name': 'Главная', 'url': '/'},
        {'name': 'Обратная связь', 'url': '/feedback/'},
        {'name': 'Отправлено', 'url': None}
    ]
    
    context = {
        'breadcrumb_items': breadcrumb_items,
    }
    
    return render(request, 'shop/feedback_success.html', context)

@login_required
def orders(request):
    """Display user's order history"""
    # Get all orders for the current user, ordered by newest first
    user_orders = (
        CatalogOrder.objects.filter(user=request.user, items__isnull=False)
        .distinct()
        .prefetch_related("items")
        .order_by("-created_at")
    )
    
    # Paginate orders (10 per page)
    paginator = Paginator(user_orders, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    breadcrumb_items = [
        {'name': 'Главная', 'url': '/'},
        {'name': 'Мои заказы', 'url': None}
    ]
    user_profile = None
    try:
        user_profile = request.user.profile
    except Exception:
        user_profile = None
    
    context = {
        'orders': page_obj,
        'breadcrumb_items': breadcrumb_items,
        "user_profile": user_profile,
        "wishlist_count": WishlistItem.objects.filter(user=request.user).count(),
        "active_tab": "orders",
    }
    
    return render(request, 'shop/orders.html', context)


@login_required
def profile_orders(request):
    """Раздел личного кабинета: история всех заказов пользователя."""
    user_orders = (
        CatalogOrder.objects.filter(user=request.user, items__isnull=False)
        .distinct()
        .prefetch_related("items")
        .order_by("-created_at")
    )
    paginator = Paginator(user_orders, 10)
    page_number = _parse_positive_int_bounded(
        request.GET.get("page"),
        default=1,
        min_value=1,
        max_value=MAX_PAGINATION_PAGE,
    )
    page_obj = paginator.get_page(page_number)

    breadcrumb_items = [
        {"name": "Главная", "url": "/"},
        {"name": "Личный кабинет", "url": reverse("profile")},
        {"name": "Мои заказы", "url": None},
    ]
    user_profile = None
    try:
        user_profile = request.user.profile
    except Exception:
        user_profile = None

    return render(
        request,
        "shop/profile_orders.html",
        {
            "orders": page_obj,
            "breadcrumb_items": breadcrumb_items,
            "page_title": "Мои покупки и заказы",
            "user_profile": user_profile,
            "wishlist_count": WishlistItem.objects.filter(user=request.user).count(),
            "active_tab": "orders",
        },
    )

@login_required
def order_detail(request, order_id):
    """Display detailed information about a specific order"""
    oid = order_id
    if not isinstance(oid, uuid.UUID):
        try:
            oid = uuid.UUID(str(order_id))
        except ValueError as err:
            raise Http404 from err
    order = get_object_or_404(
        CatalogOrder.objects.prefetch_related("items"),
        id=oid,
        user=request.user,
    )
    attach_line_display_products(order)
    
    breadcrumb_items = [
        {'name': 'Главная', 'url': '/'},
        {'name': 'Мои заказы', 'url': '/orders'},
        {'name': f'Заказ №{order.id}', 'url': None}
    ]
    user_profile = None
    try:
        user_profile = request.user.profile
    except Exception:
        user_profile = None
    
    context = {
        'order': order,
        'breadcrumb_items': breadcrumb_items,
        "user_profile": user_profile,
        "wishlist_count": WishlistItem.objects.filter(user=request.user).count(),
        "active_tab": "orders",
    }
    
    return render(request, 'shop/order_detail.html', context)


def _draw_order_pdf(order: CatalogOrder) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    margin = 34
    y = height - margin
    content_width = width - (margin * 2)
    font_name = "Helvetica"
    try:
        font_candidates = [
            Path("C:/Windows/Fonts/arial.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/dejavu/DejaVuSans.ttf"),
        ]
        for f in font_candidates:
            if f.exists():
                pdfmetrics.registerFont(TTFont("OrderFont", str(f)))
                font_name = "OrderFont"
                break
    except Exception:
        pass

    primary = colors.HexColor("#ef4444")
    primary_dark = colors.HexColor("#dc2626")
    text_main = colors.HexColor("#111827")
    text_muted = colors.HexColor("#6b7280")
    border = colors.HexColor("#e5e7eb")
    soft_bg = colors.HexColor("#f8fafc")

    def new_page():
        nonlocal y
        c.showPage()
        y = height - margin

    def ensure_space(space_needed: float):
        nonlocal y
        if y - space_needed < margin:
            new_page()

    def draw_wrapped_text(
        text: str,
        x: float,
        y_top: float,
        max_width: float,
        size: int = 11,
        color=colors.black,
        leading: float = 14,
    ) -> float:
        c.setFont(font_name, size)
        c.setFillColor(color)
        lines = simpleSplit((text or "-").strip(), font_name, size, max_width)
        cur_y = y_top
        for line in lines:
            c.drawString(x, cur_y, line)
            cur_y -= leading
        return cur_y

    # Brand header
    c.setFillColor(primary)
    c.roundRect(margin, y - 40, content_width, 42, 10, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont(font_name, 16)
    c.drawString(margin + 14, y - 24, "Береке Канц")
    c.setFont(font_name, 11)
    c.drawRightString(margin + content_width - 14, y - 22, "Подтверждение заказа")
    y -= 58

    c.setFillColor(text_main)
    c.setFont(font_name, 24)
    c.drawString(margin, y, "Спасибо за заказ!")
    y -= 26
    c.setFillColor(text_muted)
    c.setFont(font_name, 11)
    c.drawString(margin, y, "Мы получили вашу заявку и уже передали ее в обработку.")
    y -= 24

    # Order info card
    ensure_space(78)
    c.setFillColor(soft_bg)
    c.setStrokeColor(border)
    c.roundRect(margin, y - 64, content_width, 62, 10, fill=1, stroke=1)
    c.setFillColor(text_main)
    c.setFont(font_name, 11)
    c.drawString(margin + 12, y - 20, f"Номер заказа: {order.id}")
    c.drawString(margin + 12, y - 38, f"Дата оформления: {order.created_at.strftime('%d.%m.%Y %H:%M')}")
    c.setFillColor(primary_dark)
    c.setFont(font_name, 12)
    c.drawRightString(margin + content_width - 12, y - 29, f"Итого: {order.total_amount} сом")
    y -= 84

    # Order items section
    c.setFillColor(text_main)
    c.setFont(font_name, 14)
    c.drawString(margin, y, "Состав заказа")
    y -= 14

    for item in order.items.all():
        item_name = (item.name_snapshot or str(item.product_id or "")).strip() or "Товар"
        if item.special_instructions:
            item_name = f"{item_name} (отметка: {item.special_instructions})"
        qty_text = f"x {item.quantity}"
        price_text = f"{item.line_total} сом"

        wrapped_name = simpleSplit(item_name, font_name, 11, content_width - 210)
        row_height = max(30, 18 + (len(wrapped_name) - 1) * 13)
        ensure_space(row_height + 8)

        c.setFillColor(colors.white)
        c.setStrokeColor(border)
        c.roundRect(margin, y - row_height, content_width, row_height, 6, fill=1, stroke=1)
        c.setFillColor(text_main)
        c.setFont(font_name, 11)

        name_y = y - 17
        for line in wrapped_name:
            c.drawString(margin + 10, name_y, line)
            name_y -= 13

        c.setFillColor(text_muted)
        c.setFont(font_name, 10)
        c.drawString(margin + content_width - 154, y - 17, qty_text)
        c.setFillColor(primary_dark)
        c.setFont(font_name, 11)
        c.drawRightString(margin + content_width - 10, y - 17, price_text)
        y -= row_height + 8

    y -= 8

    # Delivery block
    ensure_space(150)
    c.setFillColor(text_main)
    c.setFont(font_name, 14)
    c.drawString(margin, y, "Доставка и контакты")
    y -= 12

    c.setFillColor(soft_bg)
    c.setStrokeColor(border)
    c.roundRect(margin, y - 130, content_width, 126, 10, fill=1, stroke=1)

    x_left = margin + 12
    x_right = margin + (content_width / 2) + 8
    base_y = y - 20
    left_items = [
        f"Способ доставки: {order.delivery_method_label}",
        f"Стоимость доставки: {order.shipping_fee} сом",
        f"Клиент: {order.delivery_full_name or '-'}",
    ]
    right_items = [
        f"Телефон: {order.delivery_phone or '-'}",
        f"Email: {order.delivery_email or '-'}",
    ]

    c.setFont(font_name, 10)
    c.setFillColor(text_main)
    cur_left = base_y
    for text in left_items:
        c.drawString(x_left, cur_left, text[:80])
        cur_left -= 16

    cur_right = base_y
    for text in right_items:
        c.drawString(x_right, cur_right, text[:80])
        cur_right -= 16

    address_bottom_y = draw_wrapped_text(
        f"Адрес: {order.delivery_address or '-'}",
        x_left,
        y - 74,
        content_width - 24,
        size=10,
        color=text_main,
        leading=14,
    )
    if order.customer_comment:
        draw_wrapped_text(
            f"Комментарий: {order.customer_comment}",
            x_left,
            address_bottom_y - 4,
            content_width - 24,
            size=10,
            color=text_muted,
            leading=13,
        )
    y = y - 142

    # Totals footer card
    ensure_space(90)
    c.setFillColor(colors.white)
    c.setStrokeColor(border)
    c.roundRect(margin, y - 72, content_width, 70, 10, fill=1, stroke=1)
    c.setFillColor(text_main)
    c.setFont(font_name, 11)
    c.drawString(margin + 12, y - 22, f"Сумма товаров: {order.goods_subtotal} сом")
    c.drawString(margin + 12, y - 42, f"Доставка: {order.shipping_fee} сом")
    c.setFillColor(primary)
    c.setFont(font_name, 14)
    c.drawRightString(margin + content_width - 12, y - 33, f"Итого: {order.total_amount} сом")

    c.setFillColor(text_muted)
    c.setFont(font_name, 9)
    c.drawString(margin, margin - 8, "Спасибо, что выбрали Береке Канц")
    c.showPage()
    c.save()
    return buf.getvalue()


@login_required
def order_pdf(request, order_id):
    oid = order_id
    if not isinstance(oid, uuid.UUID):
        try:
            oid = uuid.UUID(str(order_id))
        except ValueError as err:
            raise Http404 from err
    order = get_object_or_404(
        CatalogOrder.objects.prefetch_related("items"),
        id=oid,
        user=request.user,
    )

    pdf_bytes = _draw_order_pdf(order)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="order-{order.id}.pdf"'
    return response


@login_required
def order_print(request, order_id):
    oid = order_id
    if not isinstance(oid, uuid.UUID):
        try:
            oid = uuid.UUID(str(order_id))
        except ValueError as err:
            raise Http404 from err
    order = get_object_or_404(
        CatalogOrder.objects.prefetch_related("items"),
        id=oid,
        user=request.user,
    )
    return render(request, "shop/order_print.html", {"order": order})


@staff_member_required
def admin_media_proxy(request, file_path: str):
    # Serve media files for admin previews in production where /media is not publicly routed.
    normalized = (file_path or "").lstrip("/").replace("\\", "/")
    if not normalized or ".." in normalized:
        raise Http404
    if not default_storage.exists(normalized):
        raise Http404
    content_type, _ = mimetypes.guess_type(normalized)
    return FileResponse(
        default_storage.open(normalized, "rb"),
        content_type=content_type or "application/octet-stream",
    )
