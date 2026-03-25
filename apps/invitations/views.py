from urllib.parse import urlencode

from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from apps.invitations.forms import InvitationUseForm
from apps.invitations.models import Invitation
from apps.invitations.services import (
    InvalidInvitationToken,
    build_download_url,
    get_invitation_from_token,
    generate_invitation_pdf,
    generate_qr_code_png,
    inspect_invitation_token,
    consume_invitation,
    persist_validation_context,
    resolve_access_point,
)


STATUS_UI = {
    "valid": {
        "badge": "Valida",
        "headline": "Invitacion valida",
        "tone": "success",
    },
    "used": {
        "badge": "Ya utilizada",
        "headline": "Invitacion ya utilizada",
        "tone": "warning",
    },
    "cancelled": {
        "badge": "Anulada",
        "headline": "Invitacion anulada",
        "tone": "danger",
    },
    "not_found": {
        "badge": "Inexistente",
        "headline": "Invitacion inexistente",
        "tone": "neutral",
    },
}


def apply_invitation_response_security(response):
    response["Referrer-Policy"] = "no-referrer"
    return response


def wants_json_response(request) -> bool:
    return (
        request.GET.get("format") == "json"
        or request.POST.get("format") == "json"
        or "application/json" in request.headers.get("Accept", "")
    )


def build_login_url(request) -> str:
    next_url = f"{reverse('invitation-validate')}?{urlencode({'token': request.GET.get('token', '')})}"
    return f"{reverse('admin:login')}?{urlencode({'next': next_url})}"


def build_validation_context(request, outcome, form=None):
    invitation = outcome.invitation
    details = STATUS_UI[outcome.state]
    ceremony = invitation.graduate.ceremony if invitation else None
    access_point = resolve_access_point(request, ceremony, allow_session=True)

    if form is None:
        form = InvitationUseForm(
            initial={
                "token": request.GET.get("token", ""),
                "access_point": access_point.pk if access_point else None,
            },
            ceremony=ceremony,
        )

    if access_point is not None:
        persist_validation_context(request, access_point)

    return {
        "form": form,
        "outcome": outcome,
        "invitation": invitation,
        "status_badge": details["badge"],
        "status_headline": details["headline"],
        "status_tone": details["tone"],
        "can_mark_used": bool(
            invitation
            and outcome.state == "valid"
            and request.user.is_authenticated
            and request.user.is_staff
        ),
        "login_url": build_login_url(request),
        "download_url": build_download_url(invitation, request=request) if invitation else "",
    }


def render_validation_response(request, outcome, form=None, *, status_code=200):
    if wants_json_response(request):
        payload = {
            "state": outcome.state,
            "message": outcome.message,
            "marked_as_used": outcome.marked_as_used,
        }
        if outcome.invitation:
            payload["invitation"] = {
                "code": outcome.invitation.code,
                "status": outcome.invitation.status,
                "graduate": outcome.invitation.graduate.full_name,
                "ceremony": outcome.invitation.graduate.ceremony.name,
                "used_at": (
                    outcome.invitation.used_at.isoformat()
                    if outcome.invitation.used_at
                    else None
                ),
            }
        return apply_invitation_response_security(
            JsonResponse(payload, status=status_code)
        )

    context = build_validation_context(request, outcome, form=form)
    response = render(
        request,
        "invitations/validate.html",
        context,
        status=status_code,
    )
    return apply_invitation_response_security(response)


@require_GET
@never_cache
def invitation_validate_view(request):
    token = request.GET.get("token", "")
    outcome = inspect_invitation_token(token, request)
    return render_validation_response(request, outcome)


@require_POST
@staff_member_required
@never_cache
def invitation_mark_used_view(request):
    token = request.POST.get("token", "")
    try:
        preview_invitation = get_invitation_from_token(token)
        ceremony = preview_invitation.graduate.ceremony
    except InvalidInvitationToken:
        preview_invitation = None
        ceremony = None

    form = InvitationUseForm(request.POST, ceremony=ceremony)

    if not form.is_valid():
        outcome = inspect_invitation_token(token, request)
        outcome.message = "Selecciona un punto de acceso valido antes de continuar."
        return render_validation_response(request, outcome, form=form, status_code=400)

    access_point = form.cleaned_data["access_point"]
    outcome = consume_invitation(token, request, access_point=access_point)
    return render_validation_response(request, outcome, form=form)


@require_GET
@never_cache
def invitation_pdf_download_view(request):
    token = request.GET.get("token", "")
    try:
        invitation = get_invitation_from_token(token)
    except InvalidInvitationToken:
        return apply_invitation_response_security(
            HttpResponse(
                "Invitacion no disponible.",
                status=404,
                content_type="text/plain",
            )
        )
    pdf_bytes = generate_invitation_pdf(invitation, request=request)

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'inline; filename="{invitation.code.lower()}-invitacion.pdf"'
    )
    return apply_invitation_response_security(response)


@require_GET
@staff_member_required
@never_cache
def invitation_qr_view(request, public_id):
    invitation = get_object_or_404(
        Invitation.objects.select_related("graduate", "graduate__ceremony"),
        public_id=public_id,
    )
    png_bytes = generate_qr_code_png(invitation, request=request)
    return apply_invitation_response_security(
        HttpResponse(png_bytes, content_type="image/png")
    )
