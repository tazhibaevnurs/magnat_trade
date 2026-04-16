from .category_nav import build_category_nav_payload, get_shop_catalog_nav_roots_and_allowed_slugs
from .models import Cart


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
    show_static_sidebar = path.startswith("/shop")
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

    return {
        "cart_item_count": cart_item_count,
        "show_static_sidebar": show_static_sidebar,
        "is_home": is_home,
        "root_categories": root_categories,
        "catalog_categories_nav": catalog_categories_nav,
        "selected_category_slugs": selected_category_slugs,
    }