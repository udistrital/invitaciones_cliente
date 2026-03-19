from django.shortcuts import get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET

from apps.invitations.models import Invitation
from apps.invitations.services import (
    generate_invitation_pdf,
    generate_qr_code_png,
    get_invitation_from_token_or_404,
)


@require_GET
def invitation_validate_view(request):
    token = request.GET.get("token", "")
    invitation = get_invitation_from_token_or_404(token)

    return JsonResponse(
        {
            "status": "valid",
            "invitation_code": invitation.code,
            "invitation_status": invitation.status,
            "graduate": invitation.graduate.full_name,
            "ceremony": invitation.graduate.ceremony.name,
        }
    )


@require_GET
def invitation_pdf_download_view(request):
    token = request.GET.get("token", "")
    invitation = get_invitation_from_token_or_404(token)
    pdf_bytes = generate_invitation_pdf(invitation, request=request)

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'inline; filename="{invitation.code.lower()}-invitacion.pdf"'
    )
    return response


@require_GET
def invitation_qr_view(request, public_id):
    invitation = get_object_or_404(
        Invitation.objects.select_related("graduate", "graduate__ceremony"),
        public_id=public_id,
    )
    png_bytes = generate_qr_code_png(invitation, request=request)
    return HttpResponse(png_bytes, content_type="image/png")
