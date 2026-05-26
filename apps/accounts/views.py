from urllib.parse import urlparse

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
    get_safe_next_url,
    logout_user,
    persist_next_url,
    pop_next_url,
    sso_enabled,
    start_wso2_login,
)


def is_backoffice_url(url: str) -> bool:
    path = urlparse(url).path
    backoffice_root = reverse("backoffice:dashboard")
    return path == backoffice_root.rstrip("/") or path.startswith(backoffice_root)


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
        messages.error(request, str(exc))
        return HttpResponseRedirect(reverse("accounts:access-denied"))
    except (
        AuthenticationMidError,
        OIDCAuthenticationError,
        ImproperlyConfigured,
    ) as exc:
        messages.error(request, str(exc))
        return HttpResponseRedirect(reverse("accounts:access-denied"))
    except Exception:
        messages.error(
            request,
            "No fue posible completar el inicio de sesion con el proveedor institucional.",
        )
        return HttpResponseRedirect(reverse("accounts:access-denied"))

    next_url = pop_next_url(request)
    if result.user is None and is_backoffice_url(next_url):
        messages.error(
            request,
            "La cuenta autenticada no tiene el rol requerido para acceder al backoffice.",
        )
        return HttpResponseRedirect(reverse("accounts:access-denied"))

    return HttpResponseRedirect(next_url)


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
