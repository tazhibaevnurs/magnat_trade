import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email обязателен")
        email = self.normalize_email(email)
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None
    email = models.EmailField("email", unique=True)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    external_id = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        unique=True,
        db_index=True,
        help_text="Код контрагента в 1С (например НФ-000580)",
    )
    user_type = models.CharField(
        max_length=20,
        choices=[
            ("retail", "Розница"),
            ("wholesale", "Опт"),
            ("manager", "Менеджер"),
        ],
        default="retail",
        db_index=True,
    )
    entity_type = models.CharField(
        max_length=20,
        choices=[("individual", "Физлицо"), ("legal_entity", "Юрлицо")],
        default="individual",
    )
    phone = models.CharField(max_length=32, blank=True, default="")
    onec_register_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Контрагент создан в 1С",
        help_text="Время успешного ответа create_counterparty",
    )
    onec_register_error = models.TextField(
        blank=True,
        default="",
        verbose_name="Ошибка выгрузки в 1С",
        help_text="Текст последней ошибки create_counterparty (если была)",
    )
    active_session_key = models.CharField(
        max_length=40,
        blank=True,
        default="",
        db_index=True,
        help_text="Ключ сессии Django: одновременно только один активный вход (не staff).",
    )

    objects = UserManager()

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        indexes = [
            models.Index(fields=["external_id"]),
        ]

    def __str__(self) -> str:
        return self.email


class WholesaleUpgradeRequest(models.Model):
    """Заявка розничного пользователя на роль «Опт» (подтверждает менеджер)."""

    class Status(models.TextChoices):
        PENDING = "pending", "На рассмотрении"
        APPROVED = "approved", "Одобрено"
        REJECTED = "rejected", "Отклонено"

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="wholesale_upgrade_requests",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    comment = models.TextField(blank=True, help_text="Комментарий пользователя")
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_wholesale_requests",
    )
    manager_note = models.TextField(blank=True, help_text="Комментарий менеджера при отказе")

    class Meta:
        verbose_name = "Заявка на оптовый доступ"
        verbose_name_plural = "Заявки на оптовый доступ"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user.email} — {self.get_status_display()}"
