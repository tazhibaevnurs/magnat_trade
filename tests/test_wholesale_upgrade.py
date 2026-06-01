"""Одобрение заявки на опт: user_type и статус заявки."""

import pytest
from django.contrib.auth import get_user_model

from users.models import WholesaleUpgradeRequest
from users.services.wholesale_upgrade import approve_wholesale_upgrade_request

User = get_user_model()


@pytest.mark.django_db
def test_approve_wholesale_upgrade_request_sets_user_type(db):
    reviewer = User.objects.create_user(
        email="manager@test.local",
        password="pass",
        user_type="manager",
        is_staff=True,
    )
    retail = User.objects.create_user(
        email="retail-upgrade@test.local",
        password="pass",
        user_type="retail",
    )
    wr = WholesaleUpgradeRequest.objects.create(
        user=retail,
        status=WholesaleUpgradeRequest.Status.PENDING,
        comment="test",
    )

    approve_wholesale_upgrade_request(wr, reviewed_by=reviewer)

    retail.refresh_from_db()
    wr.refresh_from_db()
    assert retail.user_type == "wholesale"
    assert wr.status == WholesaleUpgradeRequest.Status.APPROVED
    assert wr.reviewed_by_id == reviewer.pk
    assert wr.reviewed_at is not None
