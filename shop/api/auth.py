import json

from django.contrib.auth import authenticate, get_user_model, login
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from ..models import UserProfile

User = get_user_model()

_AUTH_ERROR = "Неверный email или пароль."
_JSON_ERROR = "Некорректный JSON в теле запроса."


def _parse_json(request):
    try:
        body = request.body.decode("utf-8") if request.body else "{}"
        return json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


@require_http_methods(["POST"])
def handle_account_authorization(request):
    """Вход по email + пароль."""
    data = _parse_json(request)
    if data is None:
        return JsonResponse({"success": False, "err": _JSON_ERROR}, status=400)

    email = (data.get("email_address") or "").strip()
    password = data.get("password")

    if not email or not password:
        return JsonResponse({"success": False, "err": _AUTH_ERROR}, status=400)

    user = authenticate(request, username=email, password=password)

    if not user:
        return JsonResponse({"success": False, "err": _AUTH_ERROR}, status=400)

    login(request, user)
    return JsonResponse({"success": True, "redirect": "/"})


_ALLOWED_ENTITY_TYPES = frozenset({"individual", "legal_entity"})


@require_http_methods(["POST"])
def handle_account_registration(request):
    """Регистрация: email как логин, всегда розница; опт — только после одобрения менеджера и синка с 1С."""
    data = _parse_json(request)
    if data is None:
        return JsonResponse({"success": False, "err": _JSON_ERROR}, status=400)

    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    email = (data.get("email_address") or "").strip()
    password = data.get("password")
    house_address = (data.get("house_address") or "").strip()
    contact_number = (data.get("contact_number") or "").strip()
    # Игнорируем запрос опта при регистрации — всегда розница (см. заявку в профиле).
    user_type = "retail"
    entity_type = (data.get("entity_type") or "individual").strip().lower()
    if entity_type not in _ALLOWED_ENTITY_TYPES:
        return JsonResponse(
            {"success": False, "err": "Некорректный тип контрагента (физлицо/юрлицо)."},
            status=400,
        )

    if not email or not password:
        return JsonResponse(
            {"success": False, "err": "Укажите email и пароль."},
            status=400,
        )

    if User.objects.filter(email__iexact=email).exists():
        return JsonResponse(
            {"success": False, "err": "Аккаунт с таким email уже существует."},
            status=400,
        )

    user = User.objects.create_user(
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        user_type=user_type,
        entity_type=entity_type,
        phone=contact_number[:32] if contact_number else "",
    )
    UserProfile.objects.create(
        user=user,
        house_address=house_address,
        contact_number=contact_number,
    )

    from integrations.services.onec_registration import register_site_user_in_onec

    register_site_user_in_onec(user)

    login(request, user)
    return JsonResponse({"success": True, "redirect": "/"})
