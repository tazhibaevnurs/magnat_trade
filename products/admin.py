from urllib.parse import quote, urlencode

from django.contrib import admin
from django.conf import settings
from django import forms
from django.db.models import Case, IntegerField, When
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.utils.html import format_html, format_html_join

from shop.category_nav import (
    catalog_nav_restricted_tree_ids,
    get_catalog_roots_for_admin_display,
    normalize_nav_root_title,
)

from shop.services.new_arrival_items import auto_new_arrival_products_queryset

from .admin_gallery_batch import append_images_for_product, max_files_per_request
from .models import Category, Product, ProductImage


def _walk_to_category_root(obj: Category) -> Category:
    """Подъём по parent__… (до 15 уровней должно хватить после select_related)."""
    c = obj
    for _ in range(24):
        if c.parent_id is None:
            return c
        p = getattr(c, "parent", None)
        if p is None:
            return c
        c = p
    return c


def _descendant_category_ids(root_id: str) -> frozenset[str]:
    ids: set[str] = {root_id}
    frontier = [root_id]
    while frontier:
        pid = frontier.pop()
        for cid in Category.objects.filter(parent_id=pid).values_list("id", flat=True):
            if cid not in ids:
                ids.add(cid)
                frontier.append(cid)
    return frozenset(ids)


class CatalogRootSectionFilter(admin.SimpleListFilter):
    """Группы из SHOP_NAV_ROOT_CATEGORY_NAMES или все корни N-*."""

    title = "Корневой раздел"
    parameter_name = "catalog_root"

    def lookups(self, request, model_admin):
        roots = get_catalog_roots_for_admin_display()
        lookups = [(r.id, r.name) for r in roots]
        names = getattr(settings, "SHOP_NAV_ROOT_CATEGORY_NAMES", []) or []
        if names and lookups:
            lookups.append(("__other__", "Не из списка разделов"))
        return lookups

    def queryset(self, request, queryset):
        # На втором уровне (?parent__id__exact=) фильтр по корню не применим (иначе список пустой)
        if queryset.model is Category and request.GET.get("parent__id__exact"):
            return queryset
        val = self.value()
        if not val:
            return queryset
        if val == "__other__":
            names = getattr(settings, "SHOP_NAV_ROOT_CATEGORY_NAMES", []) or []
            if not names:
                return queryset
            roots = get_catalog_roots_for_admin_display()
            allowed: set[str] = set()
            for r in roots:
                allowed |= _descendant_category_ids(r.id)
            qs = queryset.exclude(pk__in=allowed)
            if queryset.model is Category:
                qs = qs.filter(parent__isnull=True)
            return qs
        tree = _descendant_category_ids(val)
        qs = queryset.filter(pk__in=tree)
        if queryset.model is Category:
            qs = qs.filter(parent__isnull=True)
        return qs


class SiteCatalogScopeFilter(admin.SimpleListFilter):
    """Совпадает с витриной: только категории/товары из деревьев SHOP_NAV_ROOT_CATEGORY_NAMES."""

    title = "Область каталога"
    parameter_name = "site_scope"

    def lookups(self, request, model_admin):
        if catalog_nav_restricted_tree_ids() is None:
            return ()
        return (("all", "Все записи в БД (включая вне сайта)"),)

    def queryset(self, request, queryset):
        restrict = catalog_nav_restricted_tree_ids()
        if restrict is None:
            return queryset
        if self.value() == "all":
            return queryset
        if queryset.model is Category:
            if request.GET.get("parent__id__exact"):
                return queryset.filter(pk__in=restrict)
            return queryset.filter(pk__in=restrict, parent__isnull=True)
        return queryset.filter(category_id__in=restrict)


class ProductCatalogRootSectionFilter(CatalogRootSectionFilter):
    """Фильтр товаров по корневому разделу (через category_id)."""

    def queryset(self, request, queryset):
        val = self.value()
        if not val:
            return queryset
        if val == "__other__":
            names = getattr(settings, "SHOP_NAV_ROOT_CATEGORY_NAMES", []) or []
            if not names:
                return queryset
            roots = get_catalog_roots_for_admin_display()
            allowed: set[str] = set()
            for r in roots:
                allowed |= _descendant_category_ids(r.id)
            return queryset.exclude(category_id__in=allowed)
        tree = _descendant_category_ids(val)
        return queryset.filter(category_id__in=tree)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0
    fields = ("image", "sort_order")
    ordering = ("sort_order", "id")

    class Media:
        js = (
            "products/admin/vendor/Sortable.min.js",
            "products/admin/product_image_sortable.js",
        )
        css = {"all": ("products/admin/product_image_sortable.css",)}


class ChildCategoryInline(admin.TabularInline):
    """Прямые подкатегории (управление деревом ниже корня)."""

    model = Category
    fk_name = "parent"
    extra = 0
    fields = ("id", "name", "slug", "is_active", "updated_at")
    readonly_fields = ("id", "slug", "updated_at")
    show_change_link = True
    verbose_name_plural = "Подкатегории"


class CategoryDirectProductInline(admin.TabularInline):
    """Товары, привязанные к этой категории (прямое поле Product.category)."""

    model = Product
    extra = 0
    fields = ("sku", "name", "retail_price", "stock", "is_active")
    readonly_fields = ("sku", "name", "retail_price", "stock", "is_active")
    ordering = ("name",)
    verbose_name_plural = "Товары в этой категории"
    show_change_link = True
    classes = ["category-direct-products-inline"]
    template = "admin/products/edit_inline/tabular_direct_products.html"

    class Media:
        css = {"all": ("admin/css/category_change.css",)}

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_formset(self, request, obj=None, **kwargs):
        formset_class = super().get_formset(request, obj, **kwargs)
        anchor = obj

        class CategoryDirectProductFormSet(formset_class):
            def get_queryset(self):
                if anchor is None:
                    return Product.objects.none()
                return Product.objects.filter(category_id=anchor.pk).order_by("name")

        return CategoryDirectProductFormSet


def _ordered_category_roots_queryset(qs):
    """Порядок корней как в SHOP_NAV_ROOT_CATEGORY_NAMES."""
    labels = getattr(settings, "SHOP_NAV_ROOT_CATEGORY_NAMES", []) or []
    roots = list(qs)
    if not labels or not roots:
        return qs.order_by("name")
    by_norm: dict[str, list[str]] = {}
    for c in roots:
        by_norm.setdefault(normalize_nav_root_title(c.name), []).append(c.pk)
    ordered_ids: list[str] = []
    seen: set[str] = set()
    for lbl in labels:
        for pk in by_norm.get(normalize_nav_root_title(lbl), []):
            if pk not in seen:
                ordered_ids.append(pk)
                seen.add(pk)
    for c in roots:
        if c.pk not in seen:
            ordered_ids.append(c.pk)
            seen.add(c.pk)
    if not ordered_ids:
        return qs.order_by("name")
    whens = [When(pk=pk, then=pos) for pos, pk in enumerate(ordered_ids)]
    return qs.filter(pk__in=ordered_ids).order_by(Case(*whens, output_field=IntegerField()))


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    change_list_template = "admin/products/category/change_list.html"
    list_display = (
        "id",
        "root_section_display",
        "name_nav",
        "products_in_section_link",
        "is_active",
        "updated_at",
    )
    list_display_links = None
    search_fields = ("name", "id")
    list_filter = (SiteCatalogScopeFilter, CatalogRootSectionFilter, "is_active")
    inlines = (ChildCategoryInline, CategoryDirectProductInline)

    def get_queryset(self, request):
        self._cl_request = request
        qs = super().get_queryset(request)
        chains = ["__".join(["parent"] * i) for i in range(1, 13)]
        qs = qs.select_related(*chains)

        rn = getattr(request, "resolver_match", None)
        url_name = getattr(rn, "url_name", "") or ""
        # Фильтры ниже только для списка; для change/delete/inlines нужен полный queryset,
        # иначе открытие подкатегории даёт «Категория с ID … не существует».
        if not url_name.endswith("_changelist"):
            return qs

        restrict = catalog_nav_restricted_tree_ids()
        site_all = request.GET.get("site_scope") == "all"
        drill_parent_id = request.GET.get("parent__id__exact")

        if drill_parent_id:
            qs = qs.filter(parent_id=drill_parent_id)
            if restrict is not None and not site_all:
                qs = qs.filter(pk__in=restrict)
            return qs.order_by("name")

        # Первый уровень: только корни (не подкатегории)
        qs = qs.filter(parent__isnull=True)

        if site_all:
            return qs.order_by("name")

        nav_names = getattr(settings, "SHOP_NAV_ROOT_CATEGORY_NAMES", []) or []
        if nav_names:
            roots_menu = get_catalog_roots_for_admin_display()
            ids = [r.pk for r in roots_menu]
            if ids:
                qs = qs.filter(pk__in=ids)
                return _ordered_category_roots_queryset(qs)

        if restrict is not None:
            qs = qs.filter(pk__in=restrict)
            return _ordered_category_roots_queryset(qs)

        # Без .env: не показывать сотни старых корней НФ-* — только дерево categoryProductList (N-*)
        if Category.objects.filter(id__startswith="N-", parent__isnull=True).exists():
            qs = qs.filter(id__startswith="N-")
        return _ordered_category_roots_queryset(qs)

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        pid = request.GET.get("parent__id__exact")
        if pid:
            try:
                parent = Category.objects.get(pk=pid)
                roots_url = reverse("admin:products_category_changelist")
                if parent.parent_id:
                    up_url = f"{roots_url}?parent__id__exact={quote(parent.parent_id)}"
                    up_label = "← Назад к подразделам"
                else:
                    up_url = roots_url
                    up_label = "← Все разделы"
                extra_context["admin_category_drill"] = {
                    "parent": parent,
                    "up_url": up_url,
                    "up_label": up_label,
                }
            except Category.DoesNotExist:
                pass
        return super().changelist_view(request, extra_context=extra_context)

    @admin.display(description="Название")
    def name_nav(self, obj: Category) -> str:
        req = getattr(self, "_cl_request", None)
        drilling = req.GET.get("parent__id__exact") if req else None
        change_url = reverse("admin:products_category_change", args=[obj.pk])
        has_children = Category.objects.filter(parent_id=obj.pk).exists()

        if obj.parent_id is None and not drilling:
            drill_url = (
                reverse("admin:products_category_changelist")
                + "?parent__id__exact="
                + quote(str(obj.pk))
            )
            return format_html('<a href="{}">{}</a>', drill_url, obj.name)

        if has_children:
            drill_url = (
                reverse("admin:products_category_changelist")
                + "?parent__id__exact="
                + quote(str(obj.pk))
            )
            return format_html(
                '<a href="{}">{}</a>'
                '&nbsp;<span style="font-weight:normal;opacity:.75">· '
                '<a href="{}">ред.</a></span>',
                drill_url,
                obj.name,
                change_url,
            )
        return format_html('<a href="{}">{}</a>', change_url, obj.name)

    @admin.display(description="Товары раздела")
    def products_in_section_link(self, obj: Category) -> str:
        root = _walk_to_category_root(obj)
        tree_ids = _descendant_category_ids(root.id)
        n = Product.objects.filter(category_id__in=tree_ids).count()
        url = reverse("admin:products_product_changelist") + "?" + urlencode({"catalog_root": root.id})
        return format_html('<a href="{}">{} шт.</a>', url, n)

    @admin.display(description="Раздел (корень)")
    def root_section_display(self, obj: Category) -> str:
        root = _walk_to_category_root(obj)
        names = getattr(settings, "SHOP_NAV_ROOT_CATEGORY_NAMES", []) or []
        if names and root.id.startswith("N-"):
            roots_menu = get_catalog_roots_for_admin_display()
            ids_menu = {r.id for r in roots_menu}
            if root.id in ids_menu:
                return root.name
            return format_html('<span title="Вне списка из SHOP_NAV_ROOT_CATEGORY_NAMES">{} · прочее</span>', root.name)
        return root.name


class AutoNovinkiListFilter(admin.SimpleListFilter):
    """Фильтр «как на /novinki/» по дате SHOP_NEW_ARRIVALS_AUTO_SINCE."""

    title = "Новинки (авто)"
    parameter_name = "auto_novinki"

    def lookups(self, request, model_admin):
        return (("1", "Попадают в авто-новинки"),)

    def queryset(self, request, queryset):
        if self.value() != "1":
            return queryset
        auto_ids = auto_new_arrival_products_queryset().values_list("pk", flat=True)
        return queryset.filter(pk__in=auto_ids)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    class ProductAdminForm(forms.ModelForm):
        class Meta:
            model = Product
            fields = "__all__"
            widgets = {
                "description": forms.Textarea(
                    attrs={
                        "rows": 10,
                        "cols": 80,
                        "class": "vLargeTextField",
                        "style": "width:100%;max-width:960px;box-sizing:border-box",
                    }
                ),
            }

    form = ProductAdminForm

    change_form_template = "admin/products/product/change_form.html"

    list_display = (
        "id",
        "image_thumb",
        "sku",
        "name",
        "catalog_root_display",
        "category",
        "retail_price",
        "stock",
        "is_active",
        "first_seen_at",
    )
    list_display_links = ("id", "name")
    search_fields = ("name", "sku", "id")
    list_filter = (
        AutoNovinkiListFilter,
        SiteCatalogScopeFilter,
        ProductCatalogRootSectionFilter,
        "is_active",
        "category",
    )
    date_hierarchy = "created_at"
    readonly_fields = ("id", "created_at", "updated_at", "gallery_preview")
    inlines = (ProductImageInline,)
    fieldsets = (
        (
            None,
            {
                "fields": ("id", "sku", "name", "category"),
                "description": "Артикул (SKU) можно оставить пустым.",
            },
        ),
        (
            "Описание для карточки на сайте",
            {
                "fields": ("description",),
                "classes": ("wide",),
            },
        ),
        (
            "Цены и склад",
            {
                "fields": ("retail_price", "wholesale_price", "stock", "unit", "is_active"),
            },
        ),
        (
            "Галерея на сайте",
            {
                "fields": ("gallery_preview",),
                "description": "Добавьте фото в таблице ниже или воспользуйтесь блоком «Массовая загрузка фото» под таблицей — файлы отправляются порциями.",
            },
        ),
        (
            "Служебное",
            {
                "fields": ("created_at", "updated_at",),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        """Явно записываем описание из формы (защита от редких сбоев связывания полей в админке)."""
        if "description" in form.cleaned_data:
            obj.description = form.cleaned_data["description"]
        super().save_model(request, obj, form, change)

    def get_urls(self):
        urls = super().get_urls()
        opts = self.opts
        info = opts.app_label, opts.model_name
        custom = [
            path(
                "<path:object_id>/gallery-batch-upload/",
                self.admin_site.admin_view(self.gallery_batch_upload_view),
                name="%s_%s_gallery_batch_upload" % info,
            ),
        ]
        return custom + urls

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}
        if object_id:
            extra_context["gallery_batch_upload_url"] = reverse(
                "admin:%s_%s_gallery_batch_upload" % (self.opts.app_label, self.opts.model_name),
                kwargs={"object_id": object_id},
            )
            extra_context["gallery_batch_files_per_batch"] = getattr(
                settings,
                "PRODUCT_GALLERY_UPLOAD_FILES_PER_BATCH",
                8,
            )
        return super().changeform_view(request, object_id, form_url, extra_context)

    def gallery_batch_upload_view(self, request, object_id):
        """AJAX: приём одной порции файлов (несколько изображений за один POST)."""
        if request.method != "POST":
            return JsonResponse({"detail": "Только POST.", "created": 0, "errors": []}, status=405)
        product = get_object_or_404(Product, pk=object_id)
        if not self.has_change_permission(request, product):
            return JsonResponse({"detail": "Недостаточно прав.", "created": 0, "errors": []}, status=403)
        files = request.FILES.getlist("images")
        max_n = max_files_per_request()
        if len(files) > max_n:
            return JsonResponse(
                {
                    "detail": f"В одном запросе не более {max_n} файлов.",
                    "created": 0,
                    "errors": [],
                },
                status=400,
            )
        if not files:
            return JsonResponse({"detail": "Не переданы файлы.", "created": 0, "errors": []}, status=400)
        created, errors = append_images_for_product(product, list(files))
        return JsonResponse({"created": created, "errors": errors, "detail": ""})

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        paths = ["category"]
        for _ in range(1, 13):
            paths.append(paths[-1] + "__parent")
        qs = qs.select_related(*paths)
        restrict = catalog_nav_restricted_tree_ids()
        if restrict is not None and request.GET.get("site_scope") != "all":
            qs = qs.filter(category_id__in=restrict)
        return qs

    @admin.display(description="Первое появление", ordering="created_at")
    def first_seen_at(self, obj: Product) -> str:
        if not obj.created_at:
            return "—"
        return obj.created_at.strftime("%Y-%m-%d %H:%M")

    @admin.display(description="Корневой раздел")
    def catalog_root_display(self, obj: Product) -> str:
        if not obj.category_id:
            return "—"
        root = _walk_to_category_root(obj.category)
        names = getattr(settings, "SHOP_NAV_ROOT_CATEGORY_NAMES", []) or []
        if names and root.id.startswith("N-"):
            roots_menu = get_catalog_roots_for_admin_display()
            ids_menu = {r.id for r in roots_menu}
            if root.id in ids_menu:
                return root.name
            return format_html(
                '<span title="Вне списка из SHOP_NAV_ROOT_CATEGORY_NAMES">{} · прочее</span>',
                root.name,
            )
        return root.name

    @admin.display(description="Фото")
    def image_thumb(self, obj: Product) -> str:
        img = obj.images.order_by("sort_order", "id").first()
        if img:
            return format_html(
                '<img src="{}" width="40" height="40" style="object-fit:cover;border-radius:4px" alt="" />',
                img.image.url,
            )
        return "—"

    @admin.display(description="Предпросмотр галереи")
    def gallery_preview(self, obj: Product) -> str:
        imgs = list(obj.images.order_by("sort_order", "id"))
        if not imgs:
            return format_html(
                '<span class="help">{}</span>',
                "Фото не добавлены — на сайте будет заглушка.",
            )
        hint = format_html(
            '<p class="help" style="margin:0 0 8px">{}</p>',
            "Перетащите миниатюры мышкой, чтобы изменить порядок на сайте (не забудьте «Сохранить» внизу страницы).",
        )
        items = format_html_join(
            "",
            '<div class="product-gallery-admin-strip-item" data-image-id="{}" role="listitem">'
            '<img src="{}" alt="" loading="lazy" /></div>',
            ((str(im.pk), im.image.url) for im in imgs),
        )
        strip = format_html(
            '<div id="product-gallery-admin-strip" class="product-gallery-admin-strip" role="list">{}</div>',
            items,
        )
        return format_html("{}{}", hint, strip)
