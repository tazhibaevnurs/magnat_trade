import json
import logging
import threading

from django.contrib.auth import authenticate, get_user_model, login
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core import signing
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import transaction
from django.http import HttpResponseBadRequest
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_bytes, force_str

from ..models import UserProfile

logger = logging.getLogger(__name__)
security_logger = logging.getLogger("security")

User = get_user_model()

_AUTH_ERROR = "Неверный email или пароль."
_JSON_ERROR = "Некорректный JSON в теле запроса."
_VERIFY_WINDOW_SECONDS = 60 * 60 * 24
_LOGIN_RATE_LIMIT = 5
_LOGIN_RATE_PERIOD_SECONDS = 60
_REGISTER_RATE_LIMIT = 3
_REGISTER_RATE_PERIOD_SECONDS = 60 * 60


def _parse_json(request):
    try:
        body = request.body.decode("utf-8") if request.body else "{}"
        return json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def _client_ident(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def _login_rate_key(request) -> str:
    ident = _client_ident(request)
    return f"auth:login-attempts:{ident}"


def _is_login_rate_limited(request) -> bool:
    attempts = cache.get(_login_rate_key(request), 0)
    return attempts >= _LOGIN_RATE_LIMIT


def _register_login_failure(request) -> int:
    key = _login_rate_key(request)
    attempts = cache.get(key, 0) + 1
    cache.set(key, attempts, timeout=_LOGIN_RATE_PERIOD_SECONDS)
    return attempts


def _reset_login_rate_limit(request) -> None:
    cache.delete(_login_rate_key(request))


def _is_registration_rate_limited(request) -> bool:
    ident = _client_ident(request)
    key = f"auth:register-attempts:{ident}"
    attempts = cache.get(key, 0)
    if attempts >= _REGISTER_RATE_LIMIT:
        return True
    cache.set(key, attempts + 1, timeout=_REGISTER_RATE_PERIOD_SECONDS)
    return False


def _verify_pow(request, purpose: str, token: str, answer: str) -> bool:
    key = f"pow:{purpose}:{token}"
    expected = cache.get(key)
    if not expected:
        return False
    if str(expected).strip() != str(answer).strip():
        return False
    cache.delete(key)
    return True


def _sanitize_next(request, raw_next: str | None) -> str:
    candidate = (raw_next or "").strip()
    if not candidate:
        return "/"
    if url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return "/"


def _make_email_verify_token(user_id: int) -> str:
    signer = signing.TimestampSigner(salt="users.email.verify")
    return signer.sign(str(user_id))


def _send_verification_email(request, user):
    token = _make_email_verify_token(user.pk)
    verify_url = request.build_absolute_uri(f"{reverse('api-verify-email')}?token={token}")
    subject = "Подтверждение email для Magnat Trade"
    body = (
        "Здравствуйте!\n\n"
        "Подтвердите ваш email, чтобы активировать аккаунт:\n"
        f"{verify_url}\n\n"
        "Ссылка действительна 24 часа."
    )
    send_mail(subject, body, None, [user.email], fail_silently=False)


def _send_password_reset_email(request, user):
    token = PasswordResetTokenGenerator().make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    reset_url = request.build_absolute_uri(f"{reverse('api-password-reset-confirm')}?uid={uid}&token={token}")
    subject = "Сброс пароля для Magnat Trade"
    body = (
        "Здравствуйте!\n\n"
        "Чтобы сбросить пароль, перейдите по ссылке:\n"
        f"{reset_url}\n\n"
        "Ссылка одноразовая и действует 1 час."
    )
    send_mail(subject, body, None, [user.email], fail_silently=False)


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

    ident = _client_ident(request)
    if _is_login_rate_limited(request):
        security_logger.warning(
            json.dumps(
                {
                    "event": "auth_login_rate_limited",
                    "ip": ident,
                    "email": email.lower(),
                },
                ensure_ascii=False,
            )
        )
        return JsonResponse(
            {
                "success": False,
                "err": "Слишком много попыток входа. Повторите через минуту.",
            },
            status=429,
        )

    user = authenticate(request, username=email, password=password)

    if not user:
        attempts = _register_login_failure(request)
        security_logger.warning(
            json.dumps(
                {
                    "event": "auth_login_failed",
                    "ip": ident,
                    "email": email.lower(),
                    "attempts_window": attempts,
                },
                ensure_ascii=False,
            )
        )
        return JsonResponse({"success": False, "err": _AUTH_ERROR}, status=400)

    login(request, user)
    _reset_login_rate_limit(request)
    security_logger.info(
        json.dumps(
            {
                "event": "auth_login_success",
                "ip": ident,
                "user_id": user.pk,
            },
            ensure_ascii=False,
        )
    )
    next_url = _sanitize_next(request, data.get("next") or request.GET.get("next"))
    return JsonResponse({"success": True, "redirect": next_url})


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
    ident = _client_ident(request)
    if _is_registration_rate_limited(request):
        security_logger.warning(
            json.dumps(
                {
                    "event": "auth_register_rate_limited",
                    "ip": ident,
                    "email": email.lower(),
                },
                ensure_ascii=False,
            )
        )
        return JsonResponse(
            {
                "success": False,
                "err": "Слишком много регистраций с этого IP. Повторите через час.",
            },
            status=429,
        )
    pow_token = (data.get("pow_token") or "").strip()
    pow_answer = (data.get("pow_answer") or "").strip()
    if not _verify_pow(request, "signup", pow_token, pow_answer):
        return JsonResponse(
            {"success": False, "err": "Проверка anti-bot не пройдена. Обновите страницу и попробуйте снова."},
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
    security_logger.info(
        json.dumps(
            {
                "event": "auth_register_success",
                "ip": ident,
                "user_id": user.pk,
            },
            ensure_ascii=False,
        )
    )
    UserProfile.objects.create(
        user=user,
        house_address=house_address,
        contact_number=contact_number,
    )

    user.is_active = True
    user.save(update_fields=["is_active"])

    uid = user.pk

    def _defer_onec_register():
        from django.db import close_old_connections

        close_old_connections()
        try:
            from integrations.services.onec_registration import register_site_user_in_onec

            fresh = User.objects.get(pk=uid)
            register_site_user_in_onec(fresh)
        except User.DoesNotExist:
            pass
        except Exception:
            logger.exception("Отложенная регистрация пользователя в 1С не удалась")
        finally:
            close_old_connections()

    def _start_background():
        threading.Thread(target=_defer_onec_register, daemon=True).start()

    transaction.on_commit(_start_background)
    try:
        _send_verification_email(request, user)
    except Exception:
        logger.exception("Не удалось отправить письмо верификации")

    return JsonResponse(
        {
            "success": True,
            "redirect": "/sign-in/",
            "message": "Аккаунт создан. Подтвердите email по ссылке из письма.",
        }
    )


@require_http_methods(["GET"])
def verify_email(request):
    token = (request.GET.get("token") or "").strip()
    if not token:
        return HttpResponseBadRequest("missing token")
    signer = signing.TimestampSigner(salt="users.email.verify")
    try:
        user_id = signer.unsign(token, max_age=_VERIFY_WINDOW_SECONDS)
    except signing.BadSignature:
        return HttpResponseBadRequest("invalid token")
    user = User.objects.filter(pk=user_id).first()
    if not user:
        return HttpResponseBadRequest("user not found")
    if not user.email_verified_at:
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified_at"])
    return redirect("/sign-in/?verified=1")


@require_http_methods(["POST"])
def password_reset_request(request):
    data = _parse_json(request)
    if data is None:
        return JsonResponse({"success": False, "err": _JSON_ERROR}, status=400)
    email = (data.get("email_address") or "").strip().lower()
    if email:
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user:
            try:
                _send_password_reset_email(request, user)
            except Exception:
                logger.exception("Не удалось отправить письмо сброса пароля")
    return JsonResponse({"success": True})


@require_http_methods(["POST"])
def password_reset_confirm(request):
    data = _parse_json(request)
    if data is None:
        return JsonResponse({"success": False, "err": _JSON_ERROR}, status=400)
    uid = (data.get("uid") or "").strip()
    token = (data.get("token") or "").strip()
    new_password = data.get("new_password") or ""
    if not uid or not token or not new_password:
        return JsonResponse({"success": False, "err": "Недостаточно данных для сброса пароля."}, status=400)
    try:
        user_id = force_str(urlsafe_base64_decode(uid))
    except Exception:
        return JsonResponse({"success": False, "err": "Некорректная ссылка сброса."}, status=400)
    user = User.objects.filter(pk=user_id, is_active=True).first()
    if not user:
        return JsonResponse({"success": False, "err": "Некорректная ссылка сброса."}, status=400)
    token_gen = PasswordResetTokenGenerator()
    if not token_gen.check_token(user, token):
        return JsonResponse({"success": False, "err": "Ссылка сброса недействительна или уже использована."}, status=400)
    try:
        validate_password(new_password, user=user)
    except ValidationError as exc:
        return JsonResponse({"success": False, "err": " ".join(exc.messages)}, status=400)
    user.set_password(new_password)
    user.save(update_fields=["password"])
    return JsonResponse({"success": True, "redirect": "/sign-in/"})
