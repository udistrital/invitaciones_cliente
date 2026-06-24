import os
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured

from apps.core.schema import INSTITUTIONAL_SEARCH_PATH


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


def get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ImproperlyConfigured(
            f"The {name} environment variable must be a numeric value."
        ) from exc


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
    "apps.accounts",
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
        "OPTIONS": {
            "options": f"-c search_path={get_env('DB_SCHEMA', INSTITUTIONAL_SEARCH_PATH)}",
        },
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
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]

APP_BASE_URL = normalize_base_url(get_env("APP_BASE_URL", "http://127.0.0.1:8000"))
USE_X_FORWARDED_FOR = get_bool("USE_X_FORWARDED_FOR", False)
VALIDATION_LOG_DEDUP_WINDOW_SECONDS = 15
SSO_ENABLED = get_bool("SSO_ENABLED", False)
OIDC_WSO2_SERVER_METADATA_URL = os.getenv("OIDC_WSO2_SERVER_METADATA_URL", "").strip()
OIDC_WSO2_AUTHORIZE_URL = os.getenv("OIDC_WSO2_AUTHORIZE_URL", "").strip()
OIDC_WSO2_TOKEN_URL = os.getenv("OIDC_WSO2_TOKEN_URL", "").strip()
OIDC_WSO2_JWKS_URL = os.getenv("OIDC_WSO2_JWKS_URL", "").strip()
OIDC_WSO2_USERINFO_URL = os.getenv("OIDC_WSO2_USERINFO_URL", "").strip()
OIDC_WSO2_END_SESSION_URL = os.getenv("OIDC_WSO2_END_SESSION_URL", "").strip()
OIDC_WSO2_ISSUER = os.getenv("OIDC_WSO2_ISSUER", "").strip()
OIDC_WSO2_REDIRECT_URL = os.getenv("OIDC_WSO2_REDIRECT_URL", "").strip()
OIDC_WSO2_CLIENT_ID = os.getenv("OIDC_WSO2_CLIENT_ID", "").strip()
OIDC_WSO2_CLIENT_SECRET = os.getenv("OIDC_WSO2_CLIENT_SECRET", "").strip()
OIDC_WSO2_SCOPES = os.getenv("OIDC_WSO2_SCOPES", "openid profile email").strip()
OIDC_WSO2_ROLE_CLAIM = os.getenv("OIDC_WSO2_ROLE_CLAIM", "roles").strip()
OIDC_WSO2_STAFF_ROLE = os.getenv("OIDC_WSO2_STAFF_ROLE", "").strip()
INSTITUTIONAL_STUDENT_ROLE = os.getenv(
    "INSTITUTIONAL_STUDENT_ROLE",
    "ESTUDIANTE",
).strip()
BACKOFFICE_REQUIRED_ROLES = (
    os.getenv("BACKOFFICE_REQUIRED_ROLES", "").strip() or OIDC_WSO2_STAFF_ROLE
)
OIDC_WSO2_EMAIL_CLAIM = os.getenv("OIDC_WSO2_EMAIL_CLAIM", "email").strip()
OIDC_WSO2_USERNAME_CLAIM = os.getenv(
    "OIDC_WSO2_USERNAME_CLAIM",
    "preferred_username",
).strip()
OIDC_WSO2_NAME_CLAIM = os.getenv("OIDC_WSO2_NAME_CLAIM", "name").strip()
OIDC_POST_LOGOUT_REDIRECT_URL = os.getenv(
    "OIDC_POST_LOGOUT_REDIRECT_URL",
    f"{APP_BASE_URL}/gestion/",
).strip()
AUTHENTICATION_MID_ENABLED = get_bool("AUTHENTICATION_MID_ENABLED", False)
AUTHENTICATION_MID_USER_ROLE_URL = os.getenv(
    "AUTHENTICATION_MID_USER_ROLE_URL",
    "https://autenticacion.portaloas.udistrital.edu.co/apioas/"
    "autenticacion_mid/v1/token/userRol",
).strip()
AUTHENTICATION_MID_TIMEOUT_SECONDS = get_float(
    "AUTHENTICATION_MID_TIMEOUT_SECONDS",
    10.0,
)
AUTHENTICATION_MID_ROLE_FIELD = os.getenv(
    "AUTHENTICATION_MID_ROLE_FIELD",
    "role",
).strip()
AUTHENTICATION_MID_DOCUMENT_FIELD = os.getenv(
    "AUTHENTICATION_MID_DOCUMENT_FIELD",
    "documento",
).strip()
AUTHENTICATION_MID_COMPOSED_DOCUMENT_FIELD = os.getenv(
    "AUTHENTICATION_MID_COMPOSED_DOCUMENT_FIELD",
    "documento_compuesto",
).strip()
AUTHENTICATION_MID_EMAIL_FIELD = os.getenv(
    "AUTHENTICATION_MID_EMAIL_FIELD",
    "email",
).strip()
AUTHENTICATION_MID_FAMILY_NAME_FIELD = os.getenv(
    "AUTHENTICATION_MID_FAMILY_NAME_FIELD",
    "FamilyName",
).strip()
AUTHENTICATION_MID_STUDENT_CODE_FIELD = os.getenv(
    "AUTHENTICATION_MID_STUDENT_CODE_FIELD",
    "Codigo",
).strip()
AUTHENTICATION_MID_STATE_FIELD = os.getenv(
    "AUTHENTICATION_MID_STATE_FIELD",
    "Estado",
).strip()

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.server": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

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
