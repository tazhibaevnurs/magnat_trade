from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User, WholesaleUpgradeRequest
from .services.wholesale_upgrade import (
    WholesaleUpgradeError,
    approve_wholesale_upgrade_request,
    reject_wholesale_upgrade_request,
)


@admin.register(WholesaleUpgradeRequest)
class WholesaleUpgradeRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "created_at", "reviewed_by", "reviewed_at")
    list_filter = ("status",)
    search_fields = ("user__email", "comment")
    readonly_fields = ("user", "created_at", "reviewed_at", "reviewed_by")
    ordering = ("-created_at",)

    def save_model(self, request, obj, form, change):
        old_status = None
        if change and obj.pk:
            old_status = (
                WholesaleUpgradeRequest.objects.filter(pk=obj.pk)
                .values_list("status", flat=True)
                .first()
            )

        super().save_model(request, obj, form, change)

        user = obj.user
        user_needs_wholesale = (
            obj.status == WholesaleUpgradeRequest.Status.APPROVED
            and user.user_type not in ("wholesale", "manager")
        )
        status_changed = old_status != obj.status

        if obj.status == WholesaleUpgradeRequest.Status.APPROVED and (
            status_changed or user_needs_wholesale
        ):
            try:
                approve_wholesale_upgrade_request(obj, reviewed_by=request.user)
            except WholesaleUpgradeError as exc:
                self.message_user(request, str(exc), level=messages.ERROR)
        elif (
            obj.status == WholesaleUpgradeRequest.Status.REJECTED
            and status_changed
        ):
            reject_wholesale_upgrade_request(
                obj,
                reviewed_by=request.user,
                manager_note=obj.manager_note,
            )


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
