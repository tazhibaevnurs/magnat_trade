from django.contrib import admin

from .models import OneCInteractionLog


@admin.register(OneCInteractionLog)
class OneCInteractionLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "direction", "method", "endpoint", "status_code", "success")
    list_filter = ("direction", "success")
    search_fields = ("endpoint", "request_id")
