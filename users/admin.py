from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User, WholesaleUpgradeRequest


@admin.register(WholesaleUpgradeRequest)
class WholesaleUpgradeRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "created_at", "reviewed_by", "reviewed_at")
    list_filter = ("status",)
    search_fields = ("user__email", "comment")
    readonly_fields = ("user", "created_at", "reviewed_at", "reviewed_by")
    ordering = ("-created_at",)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("email",)
    list_display = (
        "email",
        "first_name",
        "last_name",
        "user_type",
        "entity_type",
        "external_id",
        "onec_register_at",
        "is_staff",
    )
    search_fields = ("email", "first_name", "last_name", "phone", "external_id")
    list_filter = ("is_staff", "is_superuser", "user_type", "entity_type")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Персональные данные",
            {"fields": ("first_name", "last_name", "phone")},
        ),
        (
            "1С и тип",
            {
                "fields": (
                    "external_id",
                    "user_type",
                    "entity_type",
                    "onec_register_at",
                    "onec_register_error",
                ),
            },
        ),
        (
            "Права",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        ("Даты", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2"),
            },
        ),
    )
