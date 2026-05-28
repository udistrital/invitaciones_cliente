from functools import wraps

from django.http import HttpResponseRedirect
from django.urls import reverse

from apps.accounts.services import (
    can_view_own_invitations,
    get_sso_login_url,
    is_backoffice_operator,
    is_student_limited,
)


def redirect_to_login(request):
    return HttpResponseRedirect(get_sso_login_url(request.get_full_path()))


def redirect_student_to_invitations():
    return HttpResponseRedirect(reverse("backoffice:invitation-list"))


def backoffice_staff_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if is_backoffice_operator(request):
            return view_func(request, *args, **kwargs)

        if is_student_limited(request):
            return redirect_student_to_invitations()

        if request.user.is_authenticated:
            return HttpResponseRedirect(reverse("accounts:access-denied"))

        return redirect_to_login(request)

    return _wrapped_view


def invitation_viewer_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if can_view_own_invitations(request):
            return view_func(request, *args, **kwargs)

        if request.user.is_authenticated:
            return HttpResponseRedirect(reverse("accounts:access-denied"))

        return redirect_to_login(request)

    return _wrapped_view
