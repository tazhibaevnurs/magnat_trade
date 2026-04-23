from datetime import timedelta

from dotenv import load_dotenv
from importlib.util import find_spec
import os

load_dotenv()

"""
Django settings for magnat_trade_project.
"""

from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() in ("1", "true", "yes")

_secret_key = os.getenv("DJANGO_SECRET_KEY", "").strip()
_default_insecure = "django-insecure-change-me-in-production"
if not DEBUG:
    if not _secret_key or _secret_key == _default_insecure:
        raise ImproperlyConfigured(
            "Задайте DJANGO_SECRET_KEY в окружении (нельзя использовать значение по умолчанию при DEBUG=False)."
        )
    SECRET_KEY = _secret_key
else:
    SECRET_KEY = _secret_key or _default_insecure

# На Vercel выставляются VERCEL=1 и VERCEL_URL; поддомены *.vercel.app иначе дают DisallowedHost
_allowed_hosts = [
    h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()
]
if os.getenv("VERCEL") == "1" and ".vercel.app" not in _allowed_hosts:
    _allowed_hosts.append(".vercel.app")
if DEBUG:
    # Local dev should always accept loopback hosts,
    # even if shell environment overrides DJANGO_ALLOWED_HOSTS.
    for _local_host in ("localhost", "127.0.0.1", "[::1]"):
        if _local_host not in _allowed_hosts:
            _allowed_hosts.append(_local_host)
ALLOWED_HOSTS = _allowed_hosts

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "users",
    "products",
    "orders",
    "integrations",
    "api",
    "shop",
]
if DEBUG:
    if find_spec("django_watchfiles"):
        INSTALLED_APPS.append("django_watchfiles")
    if find_spec("django_browser_reload"):
        INSTALLED_APPS.append("django_browser_reload")

AUTH_USER_MODEL = "users.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "api.security_middleware.SecurityHeadersMiddleware",
    "api.security_middleware.SecurityAuditMiddleware",
    "api.middleware.RequestBodySizeLimitMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "users.middleware.SingleSessionPerUserMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
if DEBUG:
    if find_spec("django_browser_reload"):
        MIDDLEWARE.append("django_browser_reload.middleware.BrowserReloadMiddleware")

ROOT_URLCONF = "magnat_trade_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "shop.context_processors.cart_context",
            ],
        },
    },
]

WSGI_APPLICATION = "magnat_trade_project.wsgi.application"

# Приоритет: DATABASE_URL (PostgreSQL, деплой Vercel/Neon/Supabase) → MySQL (DB_*) → SQLite
_database_url = os.getenv("DATABASE_URL", "").strip()
_db_name = (os.getenv("DB_NAME") or "").strip()

if _database_url:
    import dj_database_url

    # Supabase Transaction pooler (pooler.supabase.com:6543) — короткие соединения; иначе Django держит пул и получают ошибки.
    # Переопределение: DATABASE_CONN_MAX_AGE=600
    _conn_raw = os.getenv("DATABASE_CONN_MAX_AGE", "").strip()
    if _conn_raw:
        try:
            _conn_max_age = int(_conn_raw)
        except ValueError:
            _conn_max_age = 600
    elif "pooler.supabase.com" in _database_url:
        _conn_max_age = 0
    else:
        _conn_max_age = 600

    DATABASES = {
        "default": dj_database_url.parse(
            _database_url,
            conn_max_age=_conn_max_age,
            conn_health_checks=True,
        )
    }
elif _db_name:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": _db_name,
            "USER": os.getenv("DB_USER"),
            "PASSWORD": os.getenv("DB_PASSWORD"),
            "HOST": os.getenv("DB_HOST", "127.0.0.1"),
            "PORT": os.getenv("DB_PORT", "3306"),
        }
    }
else:
    _sqlite_db_path = os.getenv("SQLITE_DB_PATH", "").strip()
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": _sqlite_db_path or (BASE_DIR / "db.sqlite3"),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]

LANGUAGE_CODE = "ru"
TIME_ZONE = os.getenv("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_L10N = False
USE_TZ = True

STATIC_URL = "/static/"
# Собранная статика (collectstatic) — для продакшена и Vercel; отдаётся через WhiteNoise
STATIC_ROOT = BASE_DIR / "staticfiles"
if not DEBUG:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
        },
    }

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Кэш статики в браузере (год); в DEBUG WhiteNoise не мешает dev-серверу раздавать исходники приложений
if not DEBUG:
    WHITENOISE_MAX_AGE = 31536000

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Auth (вход для @login_required, например /orders/) ---
LOGIN_URL = "/sign-in/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"
PASSWORD_RESET_TIMEOUT = int(os.getenv("PASSWORD_RESET_TIMEOUT", "3600"))

# Email verification / reset delivery
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "true").lower() in ("1", "true", "yes")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@magnat-trade.local")

# --- HTTPS / cookies (production) ---
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() in ("1", "true")
CSRF_COOKIE_SECURE = os.getenv("CSRF_COOKIE_SECURE", "false").lower() in ("1", "true")
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "false").lower() in ("1", "true")
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000")) if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv("SECURE_HSTS_INCLUDE_SUBDOMAINS", "true").lower() in (
    "1",
    "true",
    "yes",
)
SECURE_HSTS_PRELOAD = os.getenv("SECURE_HSTS_PRELOAD", "true").lower() in ("1", "true", "yes")
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
SESSION_EXPIRE_AT_BROWSER_CLOSE = os.getenv("SESSION_EXPIRE_AT_BROWSER_CLOSE", "true").lower() in (
    "1",
    "true",
    "yes",
)
SESSION_COOKIE_AGE = int(os.getenv("SESSION_COOKIE_AGE", "43200"))

# --- CORS ---
CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if o.strip()
]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = False
if not DEBUG:
    insecure_cors = [o for o in CORS_ALLOWED_ORIGINS if "localhost" in o or "127.0.0.1" in o]
    if insecure_cors:
        raise ImproperlyConfigured("Удалите localhost из CORS_ALLOWED_ORIGINS в production.")

# --- Redis / cache ---
REDIS_URL = os.getenv("REDIS_URL", "").strip()
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {},
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "magnat-trade-cache",
        }
    }

# --- Celery ---
_celery_redis = REDIS_URL or "redis://127.0.0.1:6379/0"
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", _celery_redis)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", _celery_redis)
CELERY_TASK_ALWAYS_EAGER = os.getenv("CELERY_TASK_ALWAYS_EAGER", "false").lower() in ("1", "true")
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_IGNORE_RESULT = os.getenv("CELERY_TASK_IGNORE_RESULT", "true").lower() in ("1", "true", "yes")

# Периодическая синхронизация 1С → БД (Celery Beat)
ONEC_BEAT_SYNC_ENABLED = os.getenv("ONEC_BEAT_SYNC_ENABLED", "true").lower() in ("1", "true", "yes")
# Только товары (цены, остатки): GET productList — каждые N минут (по умолчанию 5). 0 = не ставить задачу в Beat.
try:
    ONEC_BEAT_PRODUCT_SYNC_MINUTES = max(
        0,
        int(os.getenv("ONEC_BEAT_PRODUCT_SYNC_MINUTES", os.getenv("ONEC_BEAT_SYNC_MINUTES", "5"))),
    )
except ValueError:
    ONEC_BEAT_PRODUCT_SYNC_MINUTES = 5
# Полная синхронизация: категории, зеркало shop, товары, контрагенты — реже; 0 = не ставить в beat
try:
    ONEC_BEAT_FULL_SYNC_MINUTES = max(0, int(os.getenv("ONEC_BEAT_FULL_SYNC_MINUTES", "60")))
except ValueError:
    ONEC_BEAT_FULL_SYNC_MINUTES = 60

# Расписание Beat подхватывает ``celery -A magnat_trade_project beat`` (см. docker-compose: celery-beat).
CELERY_BEAT_SCHEDULE = {}
if ONEC_BEAT_SYNC_ENABLED:
    # Частое обновление только номенклатуры (productList + при необходимости categoryProductList).
    # 0 — не регистрировать задачу (остаётся только полная синхронизация раз в ONEC_BEAT_FULL_SYNC_MINUTES).
    if ONEC_BEAT_PRODUCT_SYNC_MINUTES > 0:
        CELERY_BEAT_SCHEDULE["sync-onec-product-prices"] = {
            "task": "integrations.tasks.sync_products_from_onec",
            "schedule": timedelta(minutes=ONEC_BEAT_PRODUCT_SYNC_MINUTES),
        }
    if ONEC_BEAT_FULL_SYNC_MINUTES > 0:
        CELERY_BEAT_SCHEDULE["sync-onec-full-catalog"] = {
            "task": "integrations.tasks.sync_all_from_onec",
            "schedule": timedelta(minutes=ONEC_BEAT_FULL_SYNC_MINUTES),
        }

# --- DRF ---
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": os.getenv("DRF_THROTTLE_ANON", "120/minute"),
        "user": os.getenv("DRF_THROTTLE_USER", "100/minute"),
        "integration": os.getenv("DRF_THROTTLE_INTEGRATION", "3000/minute"),
        "webhook": os.getenv("DRF_THROTTLE_WEBHOOK", "600/minute"),
        "ai_generation_free": os.getenv("DRF_THROTTLE_AI_FREE", "5/day"),
        "ai_generation_pro": os.getenv("DRF_THROTTLE_AI_PRO", "50/day"),
    },
}

DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("DATA_UPLOAD_MAX_MEMORY_SIZE", str(10 * 1024 * 1024)))
FILE_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("FILE_UPLOAD_MAX_MEMORY_SIZE", str(10 * 1024 * 1024)))

X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True

if not DEBUG:
    if not SECURE_SSL_REDIRECT:
        raise ImproperlyConfigured("SECURE_SSL_REDIRECT должен быть включён в production.")
    if not SESSION_COOKIE_SECURE:
        raise ImproperlyConfigured("SESSION_COOKIE_SECURE должен быть включён в production.")
    if not CSRF_COOKIE_SECURE:
        raise ImproperlyConfigured("CSRF_COOKIE_SECURE должен быть включён в production.")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}'
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        }
    },
    "loggers": {
        "security": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL_SECURITY", "INFO"), "propagate": False},
    },
    "root": {
        "handlers": ["console"],
        "level": os.getenv("LOG_LEVEL", "INFO"),
    },
}

# --- Интеграция 1С (HTTP-сервис, см. «Руководство к API.docx») ---
# Пример: https://rdp.it-help.kg:4443/bereke_test/hs
ONEC_API_BASE_URL = os.getenv("ONEC_API_BASE_URL", "").rstrip("/")
ONEC_AUTH_TYPE = os.getenv("ONEC_AUTH_TYPE", "basic").strip().lower()
ONEC_API_TOKEN = os.getenv("ONEC_API_TOKEN", "").strip()
ONEC_API_BASIC_USER = os.getenv("ONEC_API_BASIC_USER", "").strip()
ONEC_API_BASIC_PASSWORD = os.getenv("ONEC_API_BASIC_PASSWORD", "").strip()
# Готовая base64-строка из curl (приоритетнее пары user/password, см. integrations.clients.onec)
ONEC_API_BASIC_AUTH = os.getenv("ONEC_API_BASIC_AUTH", "").strip()
ONEC_VERIFY_SSL = os.getenv("ONEC_VERIFY_SSL", "true").lower() in ("1", "true", "yes")
# GET categories/categoryList — только если товары ссылаются на коды категорий, которых нет после categoryProductList (по умолчанию выкл.)
ONEC_LEGACY_CATEGORY_LIST_FALLBACK = os.getenv(
    "ONEC_LEGACY_CATEGORY_LIST_FALLBACK", "false"
).lower() in ("1", "true", "yes")
ONEC_SEND_EXTRA_HEADERS = os.getenv("ONEC_SEND_EXTRA_HEADERS", "true").lower() in ("1", "true", "yes")
ONEC_API_SOURCE = os.getenv("ONEC_API_SOURCE", "website")
ONEC_API_TIMEOUT = float(os.getenv("ONEC_API_TIMEOUT", "120"))
ONEC_PUSH_ON_REGISTER = os.getenv("ONEC_PUSH_ON_REGISTER", "true").lower() in ("1", "true", "yes")
# При полной синхронизации по расписанию не тянуть контрагентов (только категории + товары) — быстрее
ONEC_BEAT_SKIP_CUSTOMERS = os.getenv("ONEC_BEAT_SKIP_CUSTOMERS", "false").lower() in ("1", "true", "yes")

INTEGRATION_API_KEY = os.getenv("INTEGRATION_API_KEY", "")
INTEGRATION_BASIC_USER = os.getenv("INTEGRATION_BASIC_USER", "")
INTEGRATION_BASIC_PASSWORD = os.getenv("INTEGRATION_BASIC_PASSWORD", "")

DEFAULT_WAREHOUSE_ID = os.getenv("DEFAULT_WAREHOUSE_ID", "MAIN")
ORDER_EXPORT_TZ = os.getenv("ORDER_EXPORT_TZ", "Asia/Bishkek")

# --- Витрина: только выбранные корневые разделы из дерева categoryProductList (products.Category id N-*) ---
# Разделитель «|» сохраняет запятые внутри названия (например «Письменные товары, черчение»).
# Пусто = показывать все корни, как приходит из 1С.
_shop_nav_roots_raw = (os.getenv("SHOP_NAV_ROOT_CATEGORY_NAMES") or "").strip()
if "|" in _shop_nav_roots_raw:
    SHOP_NAV_ROOT_CATEGORY_NAMES = [x.strip() for x in _shop_nav_roots_raw.split("|") if x.strip()]
elif _shop_nav_roots_raw:
    SHOP_NAV_ROOT_CATEGORY_NAMES = [x.strip() for x in _shop_nav_roots_raw.split(",") if x.strip()]
else:
    SHOP_NAV_ROOT_CATEGORY_NAMES = []

# --- Оплата ---
PAYMENT_PROVIDER = os.getenv("PAYMENT_PROVIDER", "stub")
PAYMENT_WEBHOOK_SECRET = os.getenv("PAYMENT_WEBHOOK_SECRET", "")
PUBLIC_SITE_URL = os.getenv("PUBLIC_SITE_URL", "http://127.0.0.1:8000")
PAYMENT_RETURN_URL = os.getenv("PAYMENT_RETURN_URL", "http://127.0.0.1:8000/checkout/success/")

# --- Доставка ---
DELIVERY_PROVIDER = os.getenv("DELIVERY_PROVIDER", "mock")

# --- Telegram notifications ---
TELEGRAM_NOTIFICATIONS_ENABLED = os.getenv("TELEGRAM_NOTIFICATIONS_ENABLED", "false").lower() in (
    "1",
    "true",
    "yes",
)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_GROUP_CHAT_ID = os.getenv("TELEGRAM_GROUP_CHAT_ID", "").strip()
TELEGRAM_ASYNC_SEND = os.getenv("TELEGRAM_ASYNC_SEND", "true").lower() in ("1", "true", "yes")
try:
    TELEGRAM_HTTP_TIMEOUT = float(os.getenv("TELEGRAM_HTTP_TIMEOUT", "3"))
except ValueError:
    TELEGRAM_HTTP_TIMEOUT = 3.0
