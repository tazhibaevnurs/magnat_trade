"""Панель менеджера: заявки на опт, заказы, цены, категории, пользователи."""

from __future__ import annotations

import uuid
from decimal import Decimal, InvalidOperation
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError, Q, Value
from django.db.models.functions import Replace
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods, require_POST

from orders.models import Order
from orders.services.order_pdf import build_order_pdf, build_orders_pdf
from products.models import Category as CatalogCategory
from products.models import Product as CatalogProduct
from integrations.services.onec_registration import register_site_user_in_onec
from .category_nav import get_shop_catalog_product_category_roots
from .pricing import can_access_manager_panel
from users.models import User, WholesaleUpgradeRequest
from users.services.wholesale_upgrade import (
    WholesaleUpgradeError,
    approve_wholesale_upgrade_request,
    reject_wholesale_upgrade_request,
)

_MANAGER_TABS = frozenset({"requests", "orders", "products", "categories", "users"})
_MANAGER_ORDERS_PAGE_SIZE = 25


def _manager_initial_tab(request) -> str:
    """Какая вкладка открыта: из ?tab= или по параметрам поиска."""
    tab = (request.GET.get("tab") or "").strip().lower()
    if tab in _MANAGER_TABS:
        return tab
    if (request.GET.get("category_q") or "").strip():
        return "categories"
    if (
        (request.GET.get("q") or "").strip()
        or (request.GET.get("edit_product") or "").strip()
        or request.GET.get("include_inactive") == "1"
    ):
        return "products"
    if (request.GET.get("user_q") or "").strip():
        return "users"
    if (request.GET.get("order_q") or "").strip() or (request.GET.get("order_page") or "").strip():
        return "orders"
    return "requests"


def _manager_orders_queryset(order_q: str = ""):
    qs = (
        Order.objects.filter(items__isnull=False)
        .distinct()
        .select_related("user")
        .prefetch_related("items")
        .order_by("-created_at")
    )
    order_q = (order_q or "").strip()
    if not order_q:
        return qs
    filters = (
        Q(delivery_email__icontains=order_q)
        | Q(delivery_full_name__icontains=order_q)
        | Q(delivery_phone__icontains=order_q)
        | Q(user__email__icontains=order_q)
    )
    try:
        filters |= Q(pk=uuid.UUID(order_q))
    except ValueError:
        pass
    return qs.filter(filters)


def _orders_panel_context(request):
    order_q = (request.GET.get("order_q") or "").strip()
    orders_qs = _manager_orders_queryset(order_q)
    paginator = Paginator(orders_qs, _MANAGER_ORDERS_PAGE_SIZE)
    page_number = request.GET.get("order_page") or request.GET.get("page") or 1
    try:
        page_number = max(1, int(str(page_number).strip()))
    except (TypeError, ValueError):
        page_number = 1
    orders_page = paginator.get_page(page_number)
    return {
        "orders_page": orders_page,
        "order_q": order_q,
        "orders_total_count": paginator.count,
    }


def _products_panel_context(request):
    """Товары каталога 1С для панели: те же активные позиции, что на витрине, с расширенным поиском."""
    q = (request.GET.get("q") or "").strip()
    q_norm = " ".join(q.split())
    include_inactive = request.GET.get("include_inactive") == "1"

    products_qs = CatalogProduct.objects.select_related("category")
    if not include_inactive:
        products_qs = products_qs.filter(is_active=True)

    if q_norm:
        products_qs = products_qs.annotate(_name_ns=Replace("name", Value(" "), Value("")))
        q_compact = q_norm.replace(" ", "")
        phrase = Q(name__icontains=q_norm) | Q(sku__icontains=q_norm) | Q(pk__icontains=q_norm)
        compact = Q(_name_ns__icontains=q_compact) if q_compact else Q()
        words = [w for w in q_norm.split() if w]
        if len(words) <= 1:
            products_qs = products_qs.filter(phrase | compact)
        else:
            word_and = Q()
            for word in words:
                word_and &= Q(Q(name__icontains=word) | Q(sku__icontains=word) | Q(pk__icontains=word))
            products_qs = products_qs.filter(phrase | compact | word_and)

    products_list = products_qs.order_by("name")[:500]

    edit_pid = (request.GET.get("edit_product") or "").strip()
    edit_product = None
    if edit_pid:
        edit_product = CatalogProduct.objects.filter(pk=edit_pid).select_related("category").first()

    return {
        "products_list": products_list,
        "search_q": q,
        "include_inactive": include_inactive,
        "edit_product": edit_product,
    }


def _categories_panel_context(request):
    """Те же разделы, что на витрине (корни N-* по дереву categoryProductList)."""
    category_q = (request.GET.get("category_q") or "").strip()

    categories = list(get_shop_catalog_product_category_roots())
    if category_q:
        cq = category_q.lower()
        categories = [
            c
            for c in categories
            if cq in (c.name or "").lower()
            or cq in (c.slug or "").lower()
            or cq in str(c.pk).lower()
        ]

    return {
        "categories_list": categories,
        "category_q": category_q,
    }


def _users_panel_context(request):
    """Розница/опт без менеджеров и суперпользователей; опциональный поиск по email."""
    user_q = (request.GET.get("user_q") or "").strip()
    users_base_qs = (
        User.objects.filter(is_superuser=False)
        .exclude(user_type="manager")
        .order_by("-date_joined")
    )
    if user_q:
        users_base_qs = users_base_qs.filter(email__icontains=user_q)
    retail_users = users_base_qs.filter(user_type="retail")[:250]
    wholesale_users = users_base_qs.filter(user_type="wholesale")[:250]
    return {
        "retail_users": retail_users,
        "wholesale_users": wholesale_users,
        "user_q": user_q,
    }


def manager_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("sign-in")
        if not can_access_manager_panel(request.user):
            messages.error(request, "Раздел доступен менеджерам и персоналу сайта (is_staff).")
            return redirect("profile")
        return view_func(request, *args, **kwargs)

    return _wrapped


@login_required
@manager_required
@require_http_methods(["GET", "POST"])
def manager_dashboard(request):
    """Единая страница управления: заявки, товары, категории, пользователи."""

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == "create_category":
            return _manager_create_category(request)
        if action == "save_product_prices":
            return _manager_save_product_prices(request)
        if action == "save_category":
            return _manager_save_category(request)
        if action == "save_user":
            return _manager_save_user(request)
        if action == "create_user_manager":
            return _manager_create_user(request)

    # Старая закладка ?q=…&include_inactive=1 без tab= — открываем список разделов (категории), не поиск товара.
    if request.method == "GET":
        if not (request.GET.get("tab") or "").strip():
            if request.GET.get("include_inactive") == "1" and (request.GET.get("q") or "").strip():
                return redirect(f"{reverse('manager_dashboard')}?tab=categories")

    pending = (
        WholesaleUpgradeRequest.objects.filter(status=WholesaleUpgradeRequest.Status.PENDING)
        .select_related("user")
        .order_by("created_at")
    )
    recent_requests = WholesaleUpgradeRequest.objects.select_related("user", "reviewed_by").order_by(
        "-created_at"
    )[:30]

    products_panel = _products_panel_context(request)

    categories_panel = _categories_panel_context(request)

    users_panel = _users_panel_context(request)

    orders_panel = _orders_panel_context(request)

    breadcrumb_items = [
        {"name": "Главная", "url": "/"},
        {"name": "Профиль", "url": reverse("profile")},
        {"name": "Панель менеджера", "url": None},
    ]

    return render(
        request,
        "shop/manager_dashboard.html",
        {
            "breadcrumb_items": breadcrumb_items,
            "manager_initial_tab": _manager_initial_tab(request),
            "pending_wholesale": pending,
            "recent_wholesale": recent_requests,
            "products_list": products_panel["products_list"],
            "categories_list": categories_panel["categories_list"],
            "category_q": categories_panel["category_q"],
            "retail_users": users_panel["retail_users"],
            "wholesale_users": users_panel["wholesale_users"],
            "user_q": users_panel["user_q"],
            "search_q": products_panel["search_q"],
            "include_inactive": products_panel["include_inactive"],
            "edit_product": products_panel["edit_product"],
            "orders_page": orders_panel["orders_page"],
            "order_q": orders_panel["order_q"],
            "orders_total_count": orders_panel["orders_total_count"],
        },
    )


@login_required
@manager_required
@require_http_methods(["GET"])
def manager_orders_panel(request):
    """AJAX partial for orders block in manager dashboard."""
    return render(
        request,
        "shop/partials/manager_orders_panel.html",
        _orders_panel_context(request),
    )


@login_required
@manager_required
@require_http_methods(["GET"])
def manager_orders_pdf(request):
    """Сводный PDF всех заказов клиентов (с учётом поиска)."""
    order_q = (request.GET.get("order_q") or "").strip()
    orders = list(_manager_orders_queryset(order_q))
    pdf_bytes = build_orders_pdf(orders)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="client-orders.pdf"'
    return response


@login_required
@manager_required
@require_http_methods(["GET"])
def manager_order_pdf(request, order_id):
    """PDF одного заказа для менеджера."""
    oid = order_id
    if not isinstance(oid, uuid.UUID):
        try:
            oid = uuid.UUID(str(order_id))
        except ValueError as err:
            from django.http import Http404

            raise Http404 from err
    order = get_object_or_404(Order.objects.prefetch_related("items"), pk=oid)
    pdf_bytes = build_order_pdf(order)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="order-{order.id}.pdf"'
    return response


@login_required
@manager_required
@require_http_methods(["GET"])
def manager_products_panel(request):
    """AJAX partial for products/prices block in manager dashboard."""
    return render(
        request,
        "shop/partials/manager_products_panel.html",
        _products_panel_context(request),
    )


@login_required
@manager_required
@require_http_methods(["GET"])
def manager_categories_panel(request):
    """AJAX partial for categories block in manager dashboard."""
    return render(
        request,
        "shop/partials/manager_categories_panel.html",
        _categories_panel_context(request),
    )


@login_required
@manager_required
@require_http_methods(["GET"])
def manager_users_panel(request):
    """AJAX partial for users list in manager dashboard."""
    return render(
        request,
        "shop/partials/manager_users_panel.html",
        _users_panel_context(request),
    )


def _manager_create_category(request):
    name = (request.POST.get("name") or "").strip()
    parent_id = (request.POST.get("parent_id") or "").strip()
    if not name:
        messages.error(request, "Укажите название категории.")
        return redirect("manager_dashboard")
    base = slugify(name) or "category"
    slug = base
    n = 1
    while CatalogCategory.objects.filter(slug=slug).exists():
        slug = f"{base}-{n}"
        n += 1
    parent = None
    if parent_id:
        parent = CatalogCategory.objects.filter(pk=parent_id).first()
    new_id = f"site-{uuid.uuid4().hex}"[:64]
    CatalogCategory.objects.create(
        id=new_id,
        name=name,
        slug=slug,
        parent=parent,
        is_active=True,
    )
    messages.success(request, f"Категория «{name}» создана.")
    return redirect("manager_dashboard")


def _manager_save_product_prices(request):
    pid = (request.POST.get("product_id") or "").strip()
    if not pid:
        messages.error(request, "Не указан товар.")
        return redirect("manager_dashboard")
    p = get_object_or_404(CatalogProduct, pk=pid)
    try:
        rp = Decimal(str(request.POST.get("retail_price", "").replace(",", ".").strip()))
        wp = Decimal(str(request.POST.get("wholesale_price", "").replace(",", ".").strip()))
    except (InvalidOperation, ValueError, TypeError):
        messages.error(request, "Некорректные цены.")
        return redirect("manager_dashboard")
    p.retail_price = rp
    p.wholesale_price = wp
    p.save(update_fields=["retail_price", "wholesale_price", "updated_at"])
    messages.success(request, f"Цены обновлены: {p.name}")
    return redirect("manager_dashboard")


def _manager_save_category(request):
    cid = (request.POST.get("category_id") or "").strip()
    if not cid:
        messages.error(request, "Не указана категория.")
        return redirect("manager_dashboard")
    c = get_object_or_404(CatalogCategory, pk=cid)
    name = (request.POST.get("name") or "").strip()
    if name:
        c.name = name
    is_active = request.POST.get("is_active") == "1"
    c.is_active = is_active
    c.save(update_fields=["name", "is_active", "updated_at"])
    messages.success(request, "Категория сохранена.")
    return redirect("manager_dashboard")


def _manager_create_user(request):
    """Новый пользователь на сайте + POST …/counterparties/create_counterparty (как при регистрации)."""
    email = (request.POST.get("email") or "").strip()
    first_name = (request.POST.get("first_name") or "").strip()[:150]
    last_name = (request.POST.get("last_name") or "").strip()[:150]
    phone = (request.POST.get("phone") or "").strip()[:32]
    user_type = (request.POST.get("user_type") or "retail").strip()
    entity_type = (request.POST.get("entity_type") or "individual").strip()
    extra_comment = (request.POST.get("create_user_comment") or "").strip()[:2000]
    password = request.POST.get("password") or ""
    password_confirm = request.POST.get("password_confirm") or ""

    redirect_users = f"{reverse('manager_dashboard')}?tab=users"

    if not email:
        messages.error(request, "Укажите email.")
        return redirect(redirect_users)
    try:
        validate_email(email)
    except ValidationError:
        messages.error(request, "Некорректный email.")
        return redirect(redirect_users)

    if not password:
        messages.error(request, "Укажите пароль.")
        return redirect(redirect_users)
    if password != password_confirm:
        messages.error(request, "Пароли не совпадают.")
        return redirect(redirect_users)

    if user_type not in ("retail", "wholesale"):
        messages.error(request, "Некорректный тип цены.")
        return redirect(redirect_users)
    if entity_type not in ("individual", "legal_entity"):
        messages.error(request, "Некорректный тип контрагента.")
        return redirect(redirect_users)

    if User.objects.filter(email__iexact=email).exists():
        messages.error(request, "Пользователь с таким email уже есть.")
        return redirect(redirect_users)

    candidate = User(
        email=User.objects.normalize_email(email),
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        user_type=user_type,
        entity_type=entity_type,
        is_active=True,
    )
    try:
        validate_password(password, candidate)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect(redirect_users)

    onec_comment = "Создание из панели менеджера."
    if extra_comment:
        onec_comment = f"{onec_comment} {extra_comment}"

    try:
        with transaction.atomic():
            user = User(
                email=User.objects.normalize_email(email),
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                user_type=user_type,
                entity_type=entity_type,
                is_active=True,
            )
            user.set_password(password)
            user.save()
    except IntegrityError:
        messages.error(request, "Не удалось создать пользователя (возможно, email уже занят).")
        return redirect(redirect_users)

    register_site_user_in_onec(user, comment=onec_comment, source="website")
    user.refresh_from_db()

    if user.onec_register_at:
        messages.success(
            request,
            f"Пользователь {user.email} создан; контрагент передан в 1С (create_counterparty). "
            "Пароль задан в форме — пользователь может войти с этим паролем.",
        )
    elif user.onec_register_error:
        messages.warning(
            request,
            f"Пользователь {user.email} создан в базе сайта. Ошибка 1С: {user.onec_register_error[:500]}",
        )
    elif not (getattr(settings, "ONEC_API_BASE_URL", "") or "").strip():
        messages.success(
            request,
            f"Пользователь {user.email} создан. Выгрузка в 1С отключена (не задан ONEC_API_BASE_URL в настройках).",
        )
    elif not getattr(settings, "ONEC_PUSH_ON_REGISTER", True):
        messages.success(
            request,
            f"Пользователь {user.email} создан. ONEC_PUSH_ON_REGISTER=false — запрос в 1С не отправлялся.",
        )
    else:
        messages.success(request, f"Пользователь {user.email} создан.")

    return redirect(redirect_users)


def _manager_save_user(request):
    uid = request.POST.get("user_id")
    if not uid:
        messages.error(request, "Не указан пользователь.")
        return redirect("manager_dashboard")
    u = get_object_or_404(User, pk=uid)
    if u.is_superuser or getattr(u, "user_type", "") == "manager":
        messages.error(request, "Этого пользователя нельзя изменить из панели.")
        return redirect("manager_dashboard")
    new_type = (request.POST.get("user_type") or "retail").strip()
    if new_type not in ("retail", "wholesale"):
        messages.error(request, "Некорректный тип.")
        return redirect("manager_dashboard")
    u.user_type = new_type
    u.save(update_fields=["user_type"])
    messages.success(request, f"Тип пользователя {u.email} обновлён.")
    return redirect(f"{reverse('manager_dashboard')}?tab=users")


@require_POST
@login_required
@manager_required
def manager_wholesale_approve(request, pk: int):
    wr = get_object_or_404(
        WholesaleUpgradeRequest,
        pk=pk,
        status=WholesaleUpgradeRequest.Status.PENDING,
    )
    try:
        u = approve_wholesale_upgrade_request(wr, reviewed_by=request.user)
    except WholesaleUpgradeError as exc:
        messages.error(request, str(exc))
        return redirect("manager_dashboard")
    messages.success(request, f"Оптовый доступ выдан: {u.email}")
    return redirect("manager_dashboard")


@require_POST
@login_required
@manager_required
def manager_wholesale_reject(request, pk: int):
    wr = get_object_or_404(
        WholesaleUpgradeRequest,
        pk=pk,
        status=WholesaleUpgradeRequest.Status.PENDING,
    )
    note = (request.POST.get("manager_note") or "").strip()
    reject_wholesale_upgrade_request(wr, reviewed_by=request.user, manager_note=note)
    messages.info(request, "Заявка отклонена.")
    return redirect("manager_dashboard")


@require_POST
@login_required
@manager_required
def manager_category_delete(request, pk: str):
    c = get_object_or_404(CatalogCategory, pk=pk)
    try:
        c.delete()
        messages.success(request, "Категория удалена.")
    except ProtectedError:
        messages.error(
            request,
            "Нельзя удалить категорию: к ней привязаны товары. Сначала перенесите товары.",
        )
    return redirect("manager_dashboard")


@require_POST
@login_required
@manager_required
def manager_user_delete(request, pk: int):
    u = get_object_or_404(User, pk=pk)
    if u.pk == request.user.pk:
        messages.error(request, "Нельзя удалить свою учётную запись.")
        return redirect("manager_dashboard")
    if u.is_superuser or getattr(u, "user_type", "") == "manager":
        messages.error(request, "Нельзя удалить этого пользователя.")
        return HttpResponseForbidden("Forbidden")
    try:
        u.delete()
        messages.success(request, "Пользователь удалён.")
    except ProtectedError:
        messages.error(
            request,
            "Нельзя удалить пользователя: есть связанные заказы или данные.",
        )
    return redirect(f"{reverse('manager_dashboard')}?tab=users")
