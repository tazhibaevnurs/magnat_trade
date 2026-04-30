from .category_nav import (
    ancestor_shop_category_slugs_for_selection,
    build_category_nav_payload,
    get_shop_catalog_nav_roots_and_allowed_slugs,
)
from .models import Cart, WishlistItem


def wishlist_context(request):
    catalog_ids = frozenset()
    shop_ids = frozenset()
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        qs = WishlistItem.objects.filter(user=user)
        catalog_ids = frozenset(
            qs.exclude(catalog_product_id__isnull=True).values_list("catalog_product_id", flat=True)
        )
        shop_ids = frozenset(
            qs.exclude(shop_product_id__isnull=True).values_list("shop_product_id", flat=True)
        )
    return {
        "wishlist_catalog_ids": catalog_ids,
        "wishlist_shop_ids": shop_ids,
    }


def cart_context(request):
    """Add cart information to all template contexts"""
    cart_item_count = 0

    if hasattr(request, "user"):
        try:
            session_key = request.session.session_key
            if not session_key:
                request.session.create()
                session_key = request.session.session_key

            if request.user.is_authenticated:
                cart = Cart.objects.filter(user=request.user, is_active=True).first()
            else:
                cart = Cart.objects.filter(session_key=session_key, user=None, is_active=True).first()

            if cart:
                cart_item_count = cart.items.count()

        except Exception:
            cart_item_count = 0

    path = getattr(request, "path", "") or ""
    # Сайдбар категорий только в каталоге (/shop/), не на главной — главная на всю ширину контента
    show_static_sidebar = path.startswith("/shop") or path.startswith("/novinki") or path.startswith("/akcii")
    is_home = path == "/" or path == ""

    roots, allowed_slugs = get_shop_catalog_nav_roots_and_allowed_slugs()
    catalog_categories_nav = build_category_nav_payload(
        roots,
        allowed_descendant_slugs=allowed_slugs,
    )
    root_categories = roots

    selected_category_slugs = []
    if hasattr(request, "GET"):
        selected_category_slugs = request.GET.getlist("categories")

    catalog_nav_expand_slugs = ancestor_shop_category_slugs_for_selection(selected_category_slugs)

    out = wishlist_context(request)
    out.update(
        {
            "cart_item_count": cart_item_count,
            "show_static_sidebar": show_static_sidebar,
            "is_home": is_home,
            "root_categories": root_categories,
            "catalog_categories_nav": catalog_categories_nav,
            "selected_category_slugs": selected_category_slugs,
            "catalog_nav_expand_slugs": catalog_nav_expand_slugs,
        }
    )
    return out