from django.db import models


class OneCInteractionLog(models.Model):
    """Журнал вызовов API 1С."""

    direction = models.CharField(
        max_length=16,
        choices=[("outbound", "Сайт → 1С"), ("inbound", "1С → сайт")],
        db_index=True,
    )
    endpoint = models.CharField(max_length=512)
    method = models.CharField(max_length=16, default="POST")
    request_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    success = models.BooleanField(default=False, db_index=True)
    payload_summary = models.TextField(blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Лог 1С"
        verbose_name_plural = "Логи 1С"
        ordering = ["-created_at"]
