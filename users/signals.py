from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .models import User


@receiver(user_logged_in)
def store_active_session_key_on_login(sender, request, user: User, **kwargs):
    """Один аккаунт — одна активная сессия: при каждом входе запоминаем ключ сессии."""
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return
    sk = getattr(request.session, "session_key", None) or ""
    if not sk:
        request.session.save()
        sk = request.session.session_key or ""
    if sk:
        User.objects.filter(pk=user.pk).update(active_session_key=sk)
