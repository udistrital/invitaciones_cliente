from dataclasses import dataclass
from hashlib import sha256
from typing import Optional
from urllib.parse import urlencode

import requests
from authlib.integrations.django_client import OAuth
from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from apps.accounts.models import ExternalIdentity


WSO2_PROVIDER = ExternalIdentity.Provider.WSO2
OIDC_NEXT_SESSION_KEY = "oidc_login_next_url"
OIDC_ID_TOKEN_SESSION_KEY = "oidc_id_token"
OIDC_PROVIDER_SESSION_KEY = "oidc_provider"
AUTHENTICATION_MID_PROFILE_SESSION_KEY = "authentication_mid_profile"


class OIDCAuthenticationError(Exception):
    pass


class OIDCAccessDenied(Exception):
    pass


class AuthenticationMidError(Exception):
    pass


@dataclass(frozen=True)
class OIDCSettings:
    server_metadata_url: str
    authorize_url: str
    token_url: str
    jwks_url: str
    userinfo_url: str
    end_session_url: str
    issuer: str
    redirect_url: str
    client_id: str
    client_secret: str
    scopes: str
    role_claim: str
    staff_role: str
    email_claim: str
    username_claim: str
    name_claim: str
    post_logout_redirect_url: str


@dataclass(frozen=True)
class AuthenticationMidSettings:
    user_role_url: str
    timeout_seconds: float
    role_field: str
    document_field: str
    composed_document_field: str
    email_field: str
    family_name_field: str
    student_code_field: str
    state_field: str


@dataclass(frozen=True)
class InstitutionalProfile:
    roles: list[str]
    document: str
    composed_document: str
    email: str
    family_name: str
    student_code: str
    state: str
    raw_payload: dict

    def as_session_dict(self) -> dict:
        return {
            "roles": self.roles,
            "document": self.document,
            "composed_document": self.composed_document,
            "email": self.email,
            "family_name": self.family_name,
            "student_code": self.student_code,
            "state": self.state,
            "raw_payload": self.raw_payload,
        }


@dataclass(frozen=True)
class OIDCAuthenticationResult:
    user: Optional[object]
    claims: dict
    id_token: str
    institutional_profile: Optional[InstitutionalProfile] = None


def get_oidc_settings() -> OIDCSettings:
    required_settings = {
        "OIDC_WSO2_CLIENT_ID": getattr(settings, "OIDC_WSO2_CLIENT_ID", ""),
        "OIDC_WSO2_CLIENT_SECRET": getattr(settings, "OIDC_WSO2_CLIENT_SECRET", ""),
        "OIDC_WSO2_STAFF_ROLE": getattr(settings, "OIDC_WSO2_STAFF_ROLE", ""),
    }
    missing = [name for name, value in required_settings.items() if not value]
    if missing:
        raise ImproperlyConfigured(
            "SSO_ENABLED=True requires these settings: " + ", ".join(missing) + "."
        )

    server_metadata_url = getattr(settings, "OIDC_WSO2_SERVER_METADATA_URL", "")
    authorize_url = getattr(settings, "OIDC_WSO2_AUTHORIZE_URL", "")
    token_url = getattr(settings, "OIDC_WSO2_TOKEN_URL", "")
    jwks_url = getattr(settings, "OIDC_WSO2_JWKS_URL", "")
    manual_endpoint_settings = {
        "OIDC_WSO2_AUTHORIZE_URL": authorize_url,
        "OIDC_WSO2_TOKEN_URL": token_url,
        "OIDC_WSO2_JWKS_URL": jwks_url,
    }
    missing_manual_endpoints = [
        name for name, value in manual_endpoint_settings.items() if not value
    ]
    if not server_metadata_url and missing_manual_endpoints:
        raise ImproperlyConfigured(
            "SSO_ENABLED=True requires OIDC_WSO2_SERVER_METADATA_URL or these "
            "manual endpoint settings: "
            + ", ".join(manual_endpoint_settings.keys())
            + "."
        )

    return OIDCSettings(
        server_metadata_url=server_metadata_url,
        authorize_url=authorize_url,
        token_url=token_url,
        jwks_url=jwks_url,
        userinfo_url=getattr(settings, "OIDC_WSO2_USERINFO_URL", ""),
        end_session_url=getattr(settings, "OIDC_WSO2_END_SESSION_URL", ""),
        issuer=getattr(settings, "OIDC_WSO2_ISSUER", ""),
        redirect_url=getattr(settings, "OIDC_WSO2_REDIRECT_URL", ""),
        client_id=required_settings["OIDC_WSO2_CLIENT_ID"],
        client_secret=required_settings["OIDC_WSO2_CLIENT_SECRET"],
        scopes=getattr(settings, "OIDC_WSO2_SCOPES", "openid profile email"),
        role_claim=getattr(settings, "OIDC_WSO2_ROLE_CLAIM", "roles"),
        staff_role=required_settings["OIDC_WSO2_STAFF_ROLE"],
        email_claim=getattr(settings, "OIDC_WSO2_EMAIL_CLAIM", "email"),
        username_claim=getattr(
            settings,
            "OIDC_WSO2_USERNAME_CLAIM",
            "preferred_username",
        ),
        name_claim=getattr(settings, "OIDC_WSO2_NAME_CLAIM", "name"),
        post_logout_redirect_url=getattr(
            settings,
            "OIDC_POST_LOGOUT_REDIRECT_URL",
            f"{settings.APP_BASE_URL}/gestion/",
        ),
    )


def get_authentication_mid_settings() -> AuthenticationMidSettings:
    user_role_url = getattr(settings, "AUTHENTICATION_MID_USER_ROLE_URL", "").strip()
    if not user_role_url:
        raise ImproperlyConfigured(
            "AUTHENTICATION_MID_ENABLED=True requires AUTHENTICATION_MID_USER_ROLE_URL."
        )

    return AuthenticationMidSettings(
        user_role_url=user_role_url,
        timeout_seconds=getattr(settings, "AUTHENTICATION_MID_TIMEOUT_SECONDS", 10.0),
        role_field=getattr(settings, "AUTHENTICATION_MID_ROLE_FIELD", "role"),
        document_field=getattr(
            settings,
            "AUTHENTICATION_MID_DOCUMENT_FIELD",
            "documento",
        ),
        composed_document_field=getattr(
            settings,
            "AUTHENTICATION_MID_COMPOSED_DOCUMENT_FIELD",
            "documento_compuesto",
        ),
        email_field=getattr(settings, "AUTHENTICATION_MID_EMAIL_FIELD", "email"),
        family_name_field=getattr(
            settings,
            "AUTHENTICATION_MID_FAMILY_NAME_FIELD",
            "FamilyName",
        ),
        student_code_field=getattr(
            settings,
            "AUTHENTICATION_MID_STUDENT_CODE_FIELD",
            "Codigo",
        ),
        state_field=getattr(settings, "AUTHENTICATION_MID_STATE_FIELD", "Estado"),
    )


def sso_enabled() -> bool:
    return bool(getattr(settings, "SSO_ENABLED", False))


def authentication_mid_enabled() -> bool:
    return bool(getattr(settings, "AUTHENTICATION_MID_ENABLED", False))


def get_staff_roles() -> list[str]:
    return normalize_roles(get_oidc_settings().staff_role)


def has_staff_role(roles: list[str]) -> bool:
    return bool(set(roles).intersection(get_staff_roles()))


def get_sso_login_url(next_url: str = "") -> str:
    base_url = reverse("accounts:wso2-login")
    if not next_url:
        return base_url
    return f"{base_url}?{urlencode({'next': next_url})}"


def get_admin_login_url(next_url: str = "") -> str:
    base_url = reverse("admin:login")
    if not next_url:
        return base_url
    return f"{base_url}?{urlencode({'next': next_url})}"


def get_safe_next_url(request, next_url: str = "") -> str:
    candidate = (
        next_url or request.GET.get("next") or request.POST.get("next") or ""
    ).strip()
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return reverse("backoffice:dashboard")


def persist_next_url(request, next_url: str) -> None:
    request.session[OIDC_NEXT_SESSION_KEY] = next_url


def pop_next_url(request) -> str:
    next_url = request.session.pop(OIDC_NEXT_SESSION_KEY, "")
    if next_url:
        return next_url
    return reverse("backoffice:dashboard")


def get_wso2_oauth_client():
    config = get_oidc_settings()
    oauth = OAuth()

    client_config = {
        "name": "wso2",
        "client_id": config.client_id,
        "client_secret": config.client_secret,
        "client_kwargs": {"scope": config.scopes},
    }
    if config.authorize_url and config.token_url and config.jwks_url:
        client_config.update(
            {
                "authorize_url": config.authorize_url,
                "access_token_url": config.token_url,
                "jwks_uri": config.jwks_url,
            }
        )
        if config.userinfo_url:
            client_config["userinfo_endpoint"] = config.userinfo_url
        if config.end_session_url:
            client_config["end_session_endpoint"] = config.end_session_url
        if config.issuer:
            client_config["issuer"] = config.issuer
    else:
        client_config["server_metadata_url"] = config.server_metadata_url

    oauth.register(**client_config)
    return oauth.create_client("wso2")


def get_claim_value(claims: dict, key: str):
    if key in claims:
        return claims.get(key)

    normalized_key = key.lower()
    for existing_key, value in claims.items():
        if str(existing_key).lower() == normalized_key:
            return value
    return None


def get_institutional_email_from_claims(claims: dict) -> str:
    config = get_oidc_settings()
    candidates = [
        get_claim_value(claims, config.email_claim),
        get_claim_value(claims, "email"),
        get_claim_value(claims, config.username_claim),
        get_claim_value(claims, "preferred_username"),
        get_claim_value(claims, "upn"),
    ]
    for candidate in candidates:
        email = normalize_string(candidate)
        if email:
            return email
    return ""


def get_institutional_roles_from_payload(payload: dict) -> list[str]:
    config = get_authentication_mid_settings()
    role_candidates = [
        config.role_field,
        "role",
        "roles",
        "rol",
        "roles_institucionales",
        "userRole",
        "userRoles",
    ]
    for key in role_candidates:
        roles = normalize_roles(get_claim_value(payload, key))
        if roles:
            return roles
    return []


def build_institutional_profile(payload: dict) -> InstitutionalProfile:
    config = get_authentication_mid_settings()
    return InstitutionalProfile(
        roles=get_institutional_roles_from_payload(payload),
        document=normalize_string(get_claim_value(payload, config.document_field)),
        composed_document=normalize_string(
            get_claim_value(payload, config.composed_document_field)
        ),
        email=normalize_string(get_claim_value(payload, config.email_field)),
        family_name=normalize_string(
            get_claim_value(payload, config.family_name_field)
        ),
        student_code=normalize_string(
            get_claim_value(payload, config.student_code_field)
        ),
        state=normalize_string(get_claim_value(payload, config.state_field)),
        raw_payload=payload,
    )


def fetch_authentication_mid_profile(
    *,
    access_token: str,
    user_email: str,
) -> InstitutionalProfile:
    if not access_token:
        raise AuthenticationMidError(
            "No se recibio access_token para consultar autenticacion_mid."
        )
    if not user_email:
        raise AuthenticationMidError(
            "No se recibio correo institucional para consultar autenticacion_mid."
        )

    config = get_authentication_mid_settings()
    try:
        response = requests.post(
            config.user_role_url,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
            },
            json={"user": user_email},
            timeout=config.timeout_seconds,
        )
    except requests.RequestException as exc:
        raise AuthenticationMidError(
            "No fue posible consultar autenticacion_mid."
        ) from exc

    if response.status_code >= 400:
        raise AuthenticationMidError(
            f"autenticacion_mid respondio con estado HTTP {response.status_code}."
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise AuthenticationMidError(
            "autenticacion_mid no devolvio una respuesta JSON valida."
        ) from exc

    if not isinstance(payload, dict):
        raise AuthenticationMidError(
            "autenticacion_mid devolvio una respuesta JSON inesperada."
        )

    return build_institutional_profile(payload)


def get_authentication_mid_profile_from_session(request) -> dict:
    return request.session.get(AUTHENTICATION_MID_PROFILE_SESSION_KEY, {})


def start_wso2_login(request):
    config = get_oidc_settings()
    client = get_wso2_oauth_client()
    redirect_uri = config.redirect_url or request.build_absolute_uri(
        reverse("accounts:wso2-callback")
    )
    return client.authorize_redirect(request, redirect_uri)


def complete_wso2_authentication(request) -> OIDCAuthenticationResult:
    client = get_wso2_oauth_client()
    token = client.authorize_access_token(request)
    claims = {}
    institutional_profile = None
    user = None

    try:
        parsed_claims = client.parse_id_token(request, token)
        if parsed_claims:
            claims = dict(parsed_claims)
    except Exception:
        claims = {}

    if not claims:
        claims = dict(token.get("userinfo") or {})

    if authentication_mid_enabled():
        institutional_profile = fetch_authentication_mid_profile(
            access_token=normalize_string(token.get("access_token")),
            user_email=get_institutional_email_from_claims(claims),
        )

    request.session[OIDC_ID_TOKEN_SESSION_KEY] = token.get("id_token", "")
    request.session[OIDC_PROVIDER_SESSION_KEY] = WSO2_PROVIDER
    if institutional_profile is not None:
        request.session[AUTHENTICATION_MID_PROFILE_SESSION_KEY] = (
            institutional_profile.as_session_dict()
        )

    if institutional_profile is not None and not has_staff_role(
        institutional_profile.roles
    ):
        return OIDCAuthenticationResult(
            user=None,
            claims=claims,
            id_token=token.get("id_token", ""),
            institutional_profile=institutional_profile,
        )

    user = provision_user_from_claims(
        provider=WSO2_PROVIDER,
        claims=claims,
        roles=institutional_profile.roles if institutional_profile else None,
        email=institutional_profile.email if institutional_profile else "",
    )
    login(
        request,
        user,
        backend=getattr(
            user,
            "backend",
            settings.AUTHENTICATION_BACKENDS[0],
        ),
    )
    return OIDCAuthenticationResult(
        user=user,
        claims=claims,
        id_token=token.get("id_token", ""),
        institutional_profile=institutional_profile,
    )


def logout_user(request) -> str:
    end_session_endpoint = None
    id_token = request.session.get(OIDC_ID_TOKEN_SESSION_KEY, "")
    provider = request.session.get(OIDC_PROVIDER_SESSION_KEY, "")
    post_logout_redirect_url = (
        get_oidc_settings().post_logout_redirect_url if sso_enabled() else ""
    )

    if sso_enabled() and provider == WSO2_PROVIDER:
        client = get_wso2_oauth_client()
        try:
            metadata = client.load_server_metadata()
        except Exception:
            metadata = {}
        end_session_endpoint = metadata.get("end_session_endpoint")

    logout(request)

    if end_session_endpoint:
        query = {"post_logout_redirect_uri": post_logout_redirect_url}
        if id_token:
            query["id_token_hint"] = id_token
        return f"{end_session_endpoint}?{urlencode(query)}"

    if post_logout_redirect_url:
        return post_logout_redirect_url
    return reverse("accounts:access-denied")


def provision_user_from_claims(
    *,
    provider: str,
    claims: dict,
    roles: Optional[list[str]] = None,
    email: str = "",
):
    config = get_oidc_settings()
    issuer = (
        normalize_string(claims.get("iss"))
        or config.issuer
        or config.server_metadata_url
        or config.authorize_url
    )
    subject = str(claims.get("sub", "")).strip()

    if not subject:
        raise OIDCAuthenticationError(
            "El proveedor de identidad no devolvio el claim obligatorio 'sub'."
        )

    roles = (
        roles if roles is not None else normalize_roles(claims.get(config.role_claim))
    )
    if not has_staff_role(roles):
        raise OIDCAccessDenied(
            "La cuenta autenticada no tiene el rol requerido para acceder al backoffice."
        )

    email = normalize_string(email or claims.get(config.email_claim))
    display_name = normalize_string(claims.get(config.name_claim))
    username_claim = normalize_string(claims.get(config.username_claim))

    with transaction.atomic():
        identity = ExternalIdentity.objects.select_related("user").filter(
            provider=provider,
            issuer=issuer,
            subject=subject,
        ).first()

        if identity is not None:
            user = identity.user
        else:
            user = resolve_local_user(email=email, subject=subject)

        sync_local_user(
            user=user,
            email=email,
            display_name=display_name,
            username_claim=username_claim,
            staff=True,
        )

        identity, _ = ExternalIdentity.objects.update_or_create(
            provider=provider,
            issuer=issuer,
            subject=subject,
            defaults={
                "user": user,
                "email": email,
                "username_claim": username_claim,
                "claims_snapshot": claims,
                "last_login_at": timezone.now(),
            },
        )

    return identity.user


def resolve_local_user(*, email: str, subject: str):
    User = get_user_model()

    if email:
        existing = User.objects.filter(email__iexact=email).first()
        if existing is not None:
            return existing

    username = build_username(email=email, subject=subject)
    user = User(username=username, email=email, is_staff=True)
    user.set_unusable_password()
    return user


def sync_local_user(
    *,
    user,
    email: str,
    display_name: str,
    username_claim: str,
    staff: bool,
) -> None:
    changed_fields = []

    if email and user.email != email:
        user.email = email
        changed_fields.append("email")

    if user.is_staff != staff:
        user.is_staff = staff
        changed_fields.append("is_staff")

    first_name, last_name = split_display_name(
        display_name or username_claim or email
    )
    if first_name and user.first_name != first_name:
        user.first_name = first_name
        changed_fields.append("first_name")
    if last_name != user.last_name:
        user.last_name = last_name
        changed_fields.append("last_name")

    if not user.pk:
        user.save()
        return

    if changed_fields:
        user.save(update_fields=changed_fields)


def build_username(*, email: str, subject: str) -> str:
    if email:
        base = email.split("@", 1)[0][:120]
        username = ensure_unique_username(base)
        if username:
            return username

    hashed_subject = sha256(subject.encode("utf-8")).hexdigest()[:16]
    return ensure_unique_username(f"wso2_{hashed_subject}")


def ensure_unique_username(base_value: str) -> str:
    User = get_user_model()
    normalized = normalize_string(base_value).replace(" ", "_")[:150] or "usuario"
    candidate = normalized[:150]
    suffix = 1
    while User.objects.filter(username=candidate).exists():
        suffix_text = f"_{suffix}"
        candidate = f"{normalized[:150 - len(suffix_text)]}{suffix_text}"
        suffix += 1
    return candidate


def normalize_roles(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        if "," in value:
            return [item.strip() for item in value.split(",") if item.strip()]
        return [item.strip() for item in value.split() if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    value_as_text = str(value).strip()
    return [value_as_text] if value_as_text else []


def normalize_string(value) -> str:
    return str(value or "").strip()


def split_display_name(display_name: str) -> tuple[str, str]:
    normalized = normalize_string(display_name)
    if not normalized:
        return "", ""
    parts = normalized.split()
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])
