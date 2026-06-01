"""Одобрение/отклонение заявок на оптовый доступ (админка и панель менеджера)."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from integrations.services.onec_registration import sync_site_user_counterparty_in_onec
from users.models import User, WholesaleUpgradeRequest


class WholesaleUpgradeError(Exception):
    """Бизнес-ошибка при обработке заявки (например, цель — менеджер)."""


def approve_wholesale_upgrade_request(
    wr: WholesaleUpgradeRequest,
    *,
    reviewed_by: User | None,
) -> User:
    """Выдать опт: user_type=wholesale, заявка approved, синхронизация price_type в 1С."""
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=wr.user_id)
        if user.user_type == "manager":
            raise WholesaleUpgradeError("Нельзя назначить опт менеджеру.")
        user.user_type = "wholesale"
        user.save(update_fields=["user_type"])
        now = timezone.now()
        wr.status = WholesaleUpgradeRequest.Status.APPROVED
        wr.reviewed_by = reviewed_by
        wr.reviewed_at = now
        wr.save(update_fields=["status", "reviewed_by", "reviewed_at"])
    sync_site_user_counterparty_in_onec(user)
    return user


def reject_wholesale_upgrade_request(
    wr: WholesaleUpgradeRequest,
    *,
    reviewed_by: User | None,
    manager_note: str = "",
) -> None:
    """Отклонить заявку и зафиксировать ревью."""
    wr.status = WholesaleUpgradeRequest.Status.REJECTED
    wr.reviewed_by = reviewed_by
    wr.reviewed_at = timezone.now()
    wr.manager_note = manager_note
    wr.save(update_fields=["status", "reviewed_by", "reviewed_at", "manager_note"])
