import json
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Case, DecimalField, F, IntegerField, Q, Value, When
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
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
from .pricing import can_access_manager_panel, catalog_unit_price
from .exceptions import InsufficientStockError
from .models import Address, Cart, CartItem, Category, Feedback, Order, OrderItem, Product, UserProfile
from products.models import Product as CatalogProduct

# Главная: две полные строки при 4 колонках сетки (4 + 4)
LANDING_SECTION_LIMIT = 8


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
    """Сумма корзины, доставка и итог (для JSON и шаблона). Доставка 0, если корзина пуста."""
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
    if subtotal <= 0 or line_count == 0:
        ship = Decimal("0.00")
    elif subtotal < Decimal("200.00"):
        ship = Decimal("50.00")
    else:
        ship = Decimal("70.00")
    grand = subtotal + ship
    q = lambda d: str(d.quantize(Decimal("0.01")))
    return {
        "subtotal": q(subtotal),
        "shipping_fee": q(ship),
        "grand_total": q(grand),
        "item_count": cart.item_count(),
        "line_count": line_count,
    }


def _filter_products(request):
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


def _shop_context(request):
    """Если в БД есть товары из 1С (products.Product), показываем их; иначе — демо shop.Product."""
    if catalog_products_exist():
        qs = filter_catalog_products(request)
        paginator = Paginator(qs, 48)
        page_number = request.GET.get("page") or 1
        page_obj = paginator.get_page(page_number)
        products = [CatalogProductDisplay(p, user=request.user) for p in page_obj.object_list]
        price_min = request.GET.get("price_min", "").strip()
        price_max = request.GET.get("price_max", "").strip()
        breadcrumb_items = [
            {"name": "Главная", "url": "/"},
            {"name": "Магазин", "url": None},
        ]
        return {
            "products": products,
            "page_obj": page_obj,
            "catalog_mode": True,
            "filter_query_string": _filter_query_string(request),
            "search_query": request.GET.get("search", "").strip(),
            "selected_categories": [c for c in request.GET.getlist("categories") if c],
            "sort_by": request.GET.get("sort_by", "name"),
            "price_min": price_min,
            "price_max": price_max,
            "in_stock": in_stock_only_from_request(request),
            "breadcrumb_items": breadcrumb_items,
        }

    products, search_query, selected_categories, sort_by = _filter_products(request)
    price_min = request.GET.get("price_min", "").strip()
    price_max = request.GET.get("price_max", "").strip()
    breadcrumb_items = [
        {"name": "Главная", "url": "/"},
        {"name": "Магазин", "url": None},
    ]
    return {
        "products": products,
        "page_obj": None,
        "catalog_mode": False,
        "filter_query_string": _filter_query_string(request),
        "search_query": search_query,
        "selected_categories": selected_categories,
        "sort_by": sort_by,
        "price_min": price_min,
        "price_max": price_max,
        "in_stock": in_stock_only_from_request(request),
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
    
    context = {
        'breadcrumb_items': breadcrumb_items,
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

            if not all([name, email, subject, message_text]):
                messages.error(request, 'Заполните все обязательные поля.')
                return redirect('contact-us')

            Feedback.objects.create(
                user=request.user if request.user.is_authenticated else None,
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

    context = {
        'breadcrumb_items': breadcrumb_items,
        'category_choices': category_choices,
        'initial_data': initial_data,
    }

    return render(request, 'shop/contact-us.html', context)


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
                                },
                            )
                        else:
                            ci, created = CartItem.objects.get_or_create(
                                cart=cart,
                                product=item.product,
                                defaults={"quantity": item.quantity, "price": item.price},
                            )
                        if not created:
                            ci.quantity += item.quantity
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
    qty = int(request.POST.get("quantity", 1))

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
                defaults={"quantity": qty, "price": line_price, "product": None},
            )
            if not created:
                item.quantity += qty
                item.save(update_fields=["quantity", "updated_at"])
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
                defaults={"quantity": qty, "price": product.current_price},
            )
            if not created:
                item.quantity += qty
                item.save(update_fields=["quantity", "updated_at"])
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
            }
        )

    messages.success(request, f"«{product_name}» добавлен в корзину!")
    return redirect("cart")

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
    qty = int(request.POST.get("quantity", 0))
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
        locked.save(update_fields=["quantity", "updated_at"])
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
    from .models import InventoryTransaction
    from .services.html_catalog_order import place_order_from_catalog_cart_items

    cart = _get_or_create_cart(request)

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

    subtotal = Decimal("0.00")
    for item in items:
        if item.catalog_product_id:
            subtotal += item.price * item.quantity
        else:
            subtotal += item.product.current_price * item.quantity

    if subtotal <= 0:
        shipping_fee = Decimal("0.00")
    elif subtotal < Decimal("200.00"):
        shipping_fee = Decimal("50.00")
    else:
        shipping_fee = Decimal("70.00")

    grand_total = subtotal + shipping_fee

    if has_catalog and not request.user.is_authenticated:
        messages.info(request, "Войдите в аккаунт, чтобы оформить заказ каталога 1С.")
        return redirect(f"{reverse('sign-in')}?next={reverse('checkout')}")

    def _checkout_error_response(msg: str, full_name: str, email: str, address: str):
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
                "breadcrumb_items": breadcrumb_items,
                "checkout_form": {
                    "full_name": full_name,
                    "email": email,
                    "address": address,
                },
            },
        )

    if request.method == "POST" and "full_name" in request.POST:
        full_name = request.POST.get("full_name", "").strip()
        email = request.POST.get("email", "").strip()
        address = request.POST.get("address", "").strip()
        payment_method = request.POST.get("payment_method", "COD")

        if not all([full_name, email, address, payment_method]):
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
                    "breadcrumb_items": breadcrumb_items,
                    "checkout_form": {
                        "full_name": full_name,
                        "email": email,
                        "address": address,
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
                    address=address,
                    payment_method=payment_method,
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
                        address,
                    )
                if code.startswith("stock:"):
                    return _checkout_error_response(
                        "Не удалось зарезервировать товар. Обновите корзину и попробуйте снова.",
                        full_name,
                        email,
                        address,
                    )
                if code == "Требуется вход":
                    return redirect(f"{reverse('sign-in')}?next={reverse('checkout')}")
                return _checkout_error_response(code, full_name, email, address)

            for item in items:
                item.delete()
            if "selected_items" in request.session:
                del request.session["selected_items"]

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
            return render(
                request,
                "shop/checkout_success_catalog.html",
                {
                    "integration_order": integration_order,
                    "delivery_address": address,
                    "breadcrumb_items": breadcrumb_items,
                },
            )

        try:
            with transaction.atomic():
                order = Order.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    full_name=full_name,
                    email=email,
                    address=address,
                    payment_method=payment_method,
                    total_amount=total_amount,
                    shipping_fee=shipping_fee,
                    status="pending",
                )

                for item in items:
                    product = Product.objects.select_for_update().get(pk=item.product_id)
                    stock_before = product.stock
                    if stock_before < item.quantity:
                        raise InsufficientStockError(product.name, stock_before)
                    rows = Product.objects.filter(
                        pk=product.pk,
                        stock__gte=item.quantity,
                    ).update(stock=F("stock") - item.quantity)
                    if rows != 1:
                        raise InsufficientStockError(product.name, stock_before)
                    stock_after = stock_before - item.quantity

                    order_item = OrderItem.objects.create(
                        order=order,
                        product=item.product,
                        quantity=item.quantity,
                        price=item.product.current_price,
                    )
                    order_item.total_price = order_item.quantity * order_item.price
                    order_item.save()

                    InventoryTransaction.objects.create(
                        product=item.product,
                        order=order,
                        transaction_type="sale",
                        quantity_change=-item.quantity,
                        stock_before=stock_before,
                        stock_after=stock_after,
                        notes=f"Order #{order.id} - {full_name}",
                        created_by=request.user if request.user.is_authenticated else None,
                    )

                for item in items:
                    item.delete()

                if "selected_items" in request.session:
                    del request.session["selected_items"]

        except InsufficientStockError as exc:
            return _checkout_error_response(
                f"Недостаточно товара «{exc.product_name}». В наличии: {exc.available}",
                full_name,
                email,
                address,
            )

        breadcrumb_items = [
            {"name": "Главная", "url": "/"},
            {"name": "Корзина", "url": "/cart"},
            {"name": "Оформление заказа", "url": "/checkout"},
            {"name": "Заказ оформлен", "url": None},
        ]

        messages.success(request, f"Заказ №{order.id} успешно оформлен!")
        order = Order.objects.prefetch_related("items__product").get(pk=order.pk)
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

    context = {
        'breadcrumb_items': breadcrumb_items,
        'user': request.user,
        'user_profile': user_profile,
        'user_addresses': user_addresses,
        'wholesale_pending': wholesale_pending,
        'is_manager': can_access_manager_panel(request.user),
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
            
            # Create feedback
            feedback_obj = Feedback.objects.create(
                user=request.user if request.user.is_authenticated else None,
                name=name,
                email=email,
                category=category,
                subject=subject,
                message=message_text
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
    user_orders = Order.objects.filter(user=request.user).prefetch_related('items__product').order_by('-placed_at')
    
    # Paginate orders (10 per page)
    paginator = Paginator(user_orders, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    breadcrumb_items = [
        {'name': 'Главная', 'url': '/'},
        {'name': 'Мои заказы', 'url': None}
    ]
    
    context = {
        'orders': page_obj,
        'breadcrumb_items': breadcrumb_items,
    }
    
    return render(request, 'shop/orders.html', context)

@login_required
def order_detail(request, order_id):
    """Display detailed information about a specific order"""
    order = get_object_or_404(
        Order.objects.prefetch_related("items__product"),
        id=order_id,
        user=request.user,
    )
    
    breadcrumb_items = [
        {'name': 'Главная', 'url': '/'},
        {'name': 'Мои заказы', 'url': '/orders'},
        {'name': f'Заказ №{order.id}', 'url': None}
    ]
    
    context = {
        'order': order,
        'breadcrumb_items': breadcrumb_items,
    }
    
    return render(request, 'shop/order_detail.html', context)
