"""Создание контрагента в 1С при регистрации пользователя на сайте (POST …/create_counterparty)."""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.db import IntegrityError
from django.utils import timezone

from integrations.clients.onec import OneCAPIError, OneCClient

logger = logging.getLogger(__name__)

# Как в примере API: "external_id": "site-user-10293"
EXTERNAL_ID_PREFIX = "site-user-"


def build_create_counterparty_payload(
    user,
    *,
    comment: str | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    """
    Тело запроса в формате руководства (см. curl create_counterparty).

    {
      "external_id": "site-user-10293",
      "entity_type": "individual",
      "name": "Иванов Иван",
      "phone": "+996700123456",
      "email": "ivan@mail.com",
      "price_type": "retail",
      "is_active": true,
      "source": "website",
      "comment": "Регистрация с сайта"
    }
    """
    name = f"{user.first_name} {user.last_name}".strip() or user.email
    return {
        "external_id": f"{EXTERNAL_ID_PREFIX}{user.pk}",
        "entity_type": user.entity_type,
        "name": name,
        "phone": (user.phone or "")[:64],
        "email": user.email,
        "price_type": "wholesale" if user.user_type == "wholesale" else "retail",
        "is_active": True,
        "source": (source or "website")[:120],
        "comment": (comment or "Регистрация с сайта")[:2000],
    }


def _extract_counterparty_id_from_response(data: dict[str, Any]) -> str | None:
    """Идентификатор контрагента в 1С из JSON-ответа (разные варианты имён полей)."""
    for key in (
        "id",
        "external_id",
        "Ref_Key",
        "Ref",
        "ref",
        "Code",
        "Код",
        "Ссылка",
    ):
        raw = data.get(key)
        if raw is None:
            continue
        s = str(raw).strip()
        if s:
            return s[:64]
    return None


def _persist_register_failure(user, message: str) -> None:
    user.onec_register_error = message[:4000]
    user.save(update_fields=["onec_register_error"])


def _persist_register_success(user, onec_id: str | None) -> None:
    """Сохраняет код 1С в external_id, если он уникален; иначе — site-user-{pk} (коллизия с импортом из counterpartyList)."""
    from users.models import User

    user.onec_register_at = timezone.now()
    user.onec_register_error = ""

    fallback = f"{EXTERNAL_ID_PREFIX}{user.pk}"
    chosen = fallback
    if onec_id:
        candidate = str(onec_id).strip()[:64]
        if candidate:
            taken = User.objects.filter(external_id=candidate).exclude(pk=user.pk).exists()
            if not taken:
                chosen = candidate
            else:
                logger.warning(
                    "1С вернул id=%s, уже занят другим пользователем; для pk=%s используем %s",
                    candidate,
                    user.pk,
                    fallback,
                )

    user.external_id = chosen
    try:
        user.save(update_fields=["external_id", "onec_register_at", "onec_register_error"])
    except IntegrityError:
        logger.warning(
            "IntegrityError при external_id=%s; повтор с %s (pk=%s)",
            chosen,
            fallback,
            user.pk,
        )
        user.external_id = fallback
        try:
            user.save(update_fields=["external_id", "onec_register_at", "onec_register_error"])
        except IntegrityError:
            logger.exception(
                "Не удалось сохранить external_id даже как %s для pk=%s",
                fallback,
                user.pk,
            )
            raise


def register_site_user_in_onec(
    user,
    *,
    comment: str | None = None,
    source: str | None = None,
) -> None:
    """
    POST …/counterparties/create_counterparty.
    При ошибке 1С регистрация на сайте уже выполнена — логируем и пишем onec_register_error.
    """
    if not (getattr(settings, "ONEC_API_BASE_URL", "") or "").strip():
        return
    if not getattr(settings, "ONEC_PUSH_ON_REGISTER", True):
        return
    if getattr(user, "external_id", None):
        # Уже связан с контрагентом 1С (например импорт из списка)
        return

    payload = build_create_counterparty_payload(user, comment=comment, source=source)
    client = OneCClient()

    try:
        data = client.create_counterparty(payload)
    except OneCAPIError as exc:
        logger.warning("1С create_counterparty failed: %s", exc)
        _persist_register_failure(user, str(exc))
        return

    onec_id = _extract_counterparty_id_from_response(data) if isinstance(data, dict) else None
    _persist_register_success(user, onec_id)


def sync_site_user_counterparty_in_onec(user) -> None:
    """
    Повторная отправка контрагента в 1С с актуальным price_type (например после одобрения опта).
    В отличие от register_site_user_in_onec, не пропускает вызов при уже заданном external_id —
    предполагается, что метод create_counterparty в 1С обновляет существующую запись по external_id.
    """
    if not (getattr(settings, "ONEC_API_BASE_URL", "") or "").strip():
        return
    if not getattr(settings, "ONEC_PUSH_ON_REGISTER", True):
        return
    payload = build_create_counterparty_payload(user)
    client = OneCClient()
    try:
        data = client.create_counterparty(payload)
    except OneCAPIError as exc:
        logger.warning("1С create_counterparty (sync) failed: %s", exc)
        _persist_register_failure(user, str(exc))
        return
    onec_id = _extract_counterparty_id_from_response(data) if isinstance(data, dict) else None
    _persist_register_success(user, onec_id)
