import os
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parent.parent


def get_env(name: str, default: Optional[str] = None, required: bool = False) -> str:
    value = os.getenv(name, default)
    if required and value in (None, ""):
        raise ImproperlyConfigured(f"The {name} environment variable is required.")
    if value is None:
        raise ImproperlyConfigured(f"The {name} environment variable is required.")
    return value


def get_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def normalize_base_url(value: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ImproperlyConfigured(
            "APP_BASE_URL must be an absolute http or https URL."
        )
    if parsed.query or parsed.fragment:
        raise ImproperlyConfigured(
            "APP_BASE_URL must not include query string or fragment."
        )

    normalized_path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}{normalized_path}"


SECRET_KEY = get_env("SECRET_KEY", required=True)
DEBUG = get_bool("DEBUG", False)
ALLOWED_HOSTS = [
    host.strip()
    for host in get_env("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if host.strip()
]

if not DEBUG and SECRET_KEY.startswith("change-me"):
    raise ImproperlyConfigured(
        "SECRET_KEY must be replaced with a secure random value when DEBUG=False."
    )

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.backoffice",
    "apps.core",
    "apps.ceremonies",
    "apps.graduates",
    "apps.invitations",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": get_env("DB_NAME", required=True),
        "USER": get_env("DB_USER", required=True),
        "PASSWORD": get_env("DB_PASSWORD", required=True),
        "HOST": get_env("DB_HOST", required=True),
        "PORT": get_env("DB_PORT", "5432"),
    }
}

LANGUAGE_CODE = "es-co"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

APP_BASE_URL = normalize_base_url(get_env("APP_BASE_URL", "http://127.0.0.1:8000"))
USE_X_FORWARDED_FOR = get_bool("USE_X_FORWARDED_FOR", False)
VALIDATION_LOG_DEDUP_WINDOW_SECONDS = 15

IS_HTTPS_BASE_URL = APP_BASE_URL.startswith("https://")
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = IS_HTTPS_BASE_URL
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = IS_HTTPS_BASE_URL
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"

UNIVERSITY_NAME = "Universidad Distrital Francisco Jose de Caldas"
ACADEMIC_OFFICE_NAME = "Secretaria Academica"
INVITATION_VALIDATION_NOTE = (
    "Presente esta invitacion en el ingreso. El codigo QR es unico y su validez "
    "sera verificada al acceso."
)
