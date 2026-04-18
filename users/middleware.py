from django.contrib import messages
from django.contrib.auth import logout


class SingleSessionPerUserMiddleware:
    """
    Если пользователь вошёл с другого устройства, текущая сессия считается устаревшей и сбрасывается.
    Staff / superuser не ограничиваются (админка и несколько вкладок).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
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
