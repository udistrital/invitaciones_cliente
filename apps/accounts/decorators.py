from functools import wraps

from django.http import HttpResponseRedirect
from django.urls import reverse

from apps.accounts.services import get_sso_login_url


def backoffice_staff_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated:
            if request.user.is_staff:
                return view_func(request, *args, **kwargs)
            return HttpResponseRedirect(reverse("accounts:access-denied"))

        return HttpResponseRedirect(get_sso_login_url(request.get_full_path()))

    return _wrapped_view
