from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect


class SingleSessionPerUserMiddleware:
    """
    Если пользователь вошёл с другого устройства, текущая сессия считается устаревшей и сбрасывается.
    Staff / superuser не ограничиваются (админка и несколько вкладок).
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self._protected_prefixes = ("/profile", "/orders")

    def __call__(self, request):
        user = getattr(request, "user", None)
        if any(request.path.startswith(prefix) for prefix in self._protected_prefixes):
            if not user or not user.is_authenticated:
                login_url = getattr(settings, "LOGIN_URL", "/sign-in/")
                next_url = request.get_full_path()
                return redirect(f"{login_url}?{urlencode({'next': next_url})}")
        if (
            user
            and user.is_authenticated
            and not getattr(user, "is_staff", False)
            and not getattr(user, "is_superuser", False)
        ):
            current = getattr(request.session, "session_key", None) or ""
            stored = getattr(user, "active_session_key", None) or ""
            if stored and current and stored != current:
                logout(request)
                messages.info(
                    request,
                    "Сеанс завершён: выполнен вход в этот аккаунт с другого устройства.",
                )

        return self.get_response(request)
