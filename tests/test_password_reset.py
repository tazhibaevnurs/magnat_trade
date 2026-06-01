"""Восстановление пароля: API и ссылка в письме."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core import mail
from django.test import Client
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

User = get_user_model()


@pytest.mark.django_db
def test_password_reset_request_sends_email(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    user = User.objects.create_user(
        email="reset@test.local",
        password="old-pass-12345",
        is_active=True,
    )
    client = Client()
    r = client.post(
        reverse("api-password-reset-request"),
        data='{"email_address": "reset@test.local"}',
        content_type="application/json",
    )
    assert r.status_code == 200
    assert r.json()["success"] is True
    assert len(mail.outbox) == 1
    assert "password-reset/confirm" in mail.outbox[0].body
    assert user.email in mail.outbox[0].to


@pytest.mark.django_db
def test_password_reset_confirm_changes_password(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    user = User.objects.create_user(
        email="confirm@test.local",
        password="old-pass-12345",
        is_active=True,
    )
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = PasswordResetTokenGenerator().make_token(user)
    client = Client()
    r = client.post(
        reverse("api-password-reset-confirm"),
        data=f'{{"uid": "{uid}", "token": "{token}", "new_password": "NewPass12345"}}',
        content_type="application/json",
    )
    assert r.status_code == 200
    user.refresh_from_db()
    assert user.check_password("NewPass12345")


@pytest.mark.django_db
def test_password_reset_confirm_page_valid_link(client, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    user = User.objects.create_user(
        email="page@test.local",
        password="old-pass-12345",
        is_active=True,
    )
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = PasswordResetTokenGenerator().make_token(user)
    r = client.get(reverse("password-reset-confirm"), {"uid": uid, "token": token})
    assert r.status_code == 200
    assert b"password-reset-confirm-form" in r.content
    assert b"new_password" in r.content
