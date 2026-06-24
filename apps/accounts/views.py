import logging

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET

from apps.accounts.services import (
    AuthenticationMidError,
    OIDCAccessDenied,
    OIDCAuthenticationError,
    complete_wso2_authentication,
    get_admin_login_url,
    get_backoffice_required_roles,
    get_safe_next_url,
    has_student_role,
    logout_user,
    persist_next_url,
    pop_next_url,
    sso_enabled,
    start_wso2_login,
)

logger = logging.getLogger(__name__)


@require_GET
def wso2_login_view(request):
    next_url = get_safe_next_url(request)
    persist_next_url(request, next_url)

    if not sso_enabled():
        return HttpResponseRedirect(get_admin_login_url(next_url))

    return start_wso2_login(request)


@require_GET
def wso2_callback_view(request):
    if not sso_enabled():
        return HttpResponseRedirect(get_admin_login_url(pop_next_url(request)))

    try:
        result = complete_wso2_authentication(request)
    except OIDCAccessDenied as exc:
        logger.warning("SSO callback denied: %s", exc)
        messages.error(request, str(exc))
        return HttpResponseRedirect(reverse("accounts:access-denied"))
    except (
        AuthenticationMidError,
        OIDCAuthenticationError,
        ImproperlyConfigured,
    ) as exc:
        logger.warning(
            "SSO callback failed reason=%s error=%s",
            exc.__class__.__name__,
            exc,
        )
        messages.error(request, str(exc))
        return HttpResponseRedirect(reverse("accounts:access-denied"))
    except Exception:
        logger.exception("SSO callback failed with unexpected error")
        messages.error(
            request,
            "No fue posible completar el inicio de sesion con el proveedor institucional.",
        )
        return HttpResponseRedirect(reverse("accounts:access-denied"))

    next_url = pop_next_url(request)
    if result.user is None and result.institutional_profile is not None:
        if has_student_role(result.institutional_profile.roles):
            return HttpResponseRedirect(reverse("backoffice:invitation-list"))

    if result.user is None:
        institutional_profile = result.institutional_profile
        logger.warning(
            "SSO callback denied without local user email=%s roles=%s required_roles=%s",
            institutional_profile.email if institutional_profile else "",
            ",".join(institutional_profile.roles) if institutional_profile else "",
            ",".join(get_backoffice_required_roles()),
        )
        detail = (
            "La cuenta autenticada no tiene el rol requerido para acceder al backoffice."
        )
        if settings.DEBUG and result.institutional_profile is not None:
            received_roles = ", ".join(result.institutional_profile.roles) or "ninguno"
            required_roles = ", ".join(get_backoffice_required_roles()) or "ninguno"
            detail = (
                f"{detail} Roles recibidos desde autenticacion_mid: "
                f"{received_roles}. Roles requeridos: {required_roles}."
            )
        messages.error(request, detail)
        return HttpResponseRedirect(reverse("accounts:access-denied"))

    return HttpResponseRedirect(next_url)


@require_GET
def wso2_root_callback_view(request):
    if request.GET.get("code") or request.GET.get("error"):
        return wso2_callback_view(request)
    return HttpResponseRedirect(reverse("backoffice:dashboard"))


@require_GET
def access_denied_view(request):
    return render(
        request,
        "accounts/access_denied.html",
        status=403,
        context={
            "page_title": "Acceso denegado",
            "login_url": get_admin_login_url()
            if not sso_enabled()
            else reverse("accounts:wso2-login"),
        },
    )


@require_GET
def logout_view(request):
    return HttpResponseRedirect(logout_user(request))
