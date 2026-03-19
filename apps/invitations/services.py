import hashlib
import io
from urllib.parse import urlencode
from typing import List

import qrcode
from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.http import Http404
from django.urls import reverse
from django.utils import timezone
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from apps.graduates.models import Graduate
from apps.invitations.models import Invitation


INVITATION_TOKEN_SALT = "apps.invitations.token"


class InvalidInvitationToken(Exception):
    pass


def generate_invitation_token(invitation: Invitation) -> str:
    signer = signing.Signer(salt=INVITATION_TOKEN_SALT)
    payload = {
        "invitation": str(invitation.public_id),
        "version": invitation.token_version,
    }
    return signer.sign_object(payload, compress=False)


def get_token_fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16].upper()


def get_invitation_from_token(token: str) -> Invitation:
    signer = signing.Signer(salt=INVITATION_TOKEN_SALT)

    try:
        payload = signer.unsign_object(token)
    except signing.BadSignature as exc:
        raise InvalidInvitationToken("La firma del token no es válida.") from exc

    public_id = payload.get("invitation")
    token_version = payload.get("version")

    if not public_id or not token_version:
        raise InvalidInvitationToken("El token no contiene una carga válida.")

    try:
        invitation = Invitation.objects.select_related(
            "graduate",
            "graduate__ceremony",
        ).get(public_id=public_id)
    except Invitation.DoesNotExist as exc:
        raise InvalidInvitationToken("La invitación no existe.") from exc

    if invitation.token_version != token_version:
        raise InvalidInvitationToken("El token de la invitación fue reemplazado.")

    return invitation


def get_invitation_from_token_or_404(token: str) -> Invitation:
    try:
        return get_invitation_from_token(token)
    except InvalidInvitationToken as exc:
        raise Http404(str(exc)) from exc


def build_absolute_url(path: str, request=None) -> str:
    if request is not None:
        return request.build_absolute_uri(path)
    return f"{settings.APP_BASE_URL.rstrip('/')}{path}"


def build_validation_url(invitation: Invitation, request=None) -> str:
    token = generate_invitation_token(invitation)
    path = f"{reverse('invitation-validate')}?{urlencode({'token': token})}"
    return build_absolute_url(path, request=request)


def build_download_url(invitation: Invitation, request=None) -> str:
    token = generate_invitation_token(invitation)
    path = f"{reverse('invitation-download-pdf')}?{urlencode({'token': token})}"
    return build_absolute_url(path, request=request)


def generate_qr_code_png(invitation: Invitation, request=None) -> bytes:
    validation_url = build_validation_url(invitation, request=request)
    qr = qrcode.QRCode(
        version=None,
        box_size=6,
        border=2,
    )
    qr.add_data(validation_url)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def format_event_datetime(invitation: Invitation) -> tuple[str, str]:
    event_dt = timezone.localtime(invitation.graduate.ceremony.scheduled_at)
    return event_dt.strftime("%d/%m/%Y"), event_dt.strftime("%I:%M %p")


def generate_invitation_pdf(invitation: Invitation, request=None) -> bytes:
    pdf_buffer = io.BytesIO()
    pdf = canvas.Canvas(pdf_buffer, pagesize=A4, pageCompression=0)
    width, height = A4
    qr_buffer = io.BytesIO(generate_qr_code_png(invitation, request=request))
    qr_image = ImageReader(qr_buffer)
    event_date, event_time = format_event_datetime(invitation)

    y = height - 72
    pdf.setTitle(f"Invitacion {invitation.code}")
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(72, y, settings.UNIVERSITY_NAME)
    y -= 24
    pdf.setFont("Helvetica", 13)
    pdf.drawString(72, y, settings.ACADEMIC_OFFICE_NAME)
    y -= 36

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(72, y, "Invitacion de ceremonia de grado")
    y -= 28

    pdf.setFont("Helvetica", 11)
    lines = [
        f"Graduando: {invitation.graduate.full_name}",
        f"Programa academico: {invitation.graduate.academic_program}",
        f"Fecha: {event_date}",
        f"Hora: {event_time}",
        f"Lugar: {invitation.graduate.ceremony.venue}",
        f"Codigo de invitacion: {invitation.code}",
    ]

    for line in lines:
        pdf.drawString(72, y, line)
        y -= 20

    pdf.drawImage(qr_image, width - 200, height - 300, width=120, height=120)

    note = settings.INVITATION_VALIDATION_NOTE
    text_object = pdf.beginText(72, y - 16)
    text_object.setFont("Helvetica", 10)
    for line in split_text(note, 72):
        text_object.textLine(line)
    pdf.drawText(text_object)

    pdf.setFont("Helvetica-Oblique", 9)
    pdf.drawString(72, 72, f"Validacion: {build_validation_url(invitation, request=request)}")

    pdf.showPage()
    pdf.save()
    return pdf_buffer.getvalue()


def split_text(text: str, max_chars: int) -> List[str]:
    words = text.split()
    lines: List[str] = []
    current_line: List[str] = []
    current_size = 0

    for word in words:
        extra = len(word) if not current_line else len(word) + 1
        if current_size + extra > max_chars:
            lines.append(" ".join(current_line))
            current_line = [word]
            current_size = len(word)
            continue
        current_line.append(word)
        current_size += extra

    if current_line:
        lines.append(" ".join(current_line))

    return lines


def issue_invitations_for_graduate(graduate: Graduate) -> List[Invitation]:
    invitations = []
    existing_by_sequence = {
        invitation.sequence_number: invitation
        for invitation in graduate.invitations.all()
    }

    for sequence_number in range(1, graduate.invitation_quota + 1):
        invitation = existing_by_sequence.get(sequence_number)
        if invitation is None:
            invitation = Invitation.objects.create(
                graduate=graduate,
                sequence_number=sequence_number,
            )
        invitations.append(invitation)

    return invitations


def rotate_invitation_token(invitation: Invitation) -> Invitation:
    if invitation.status == Invitation.Status.CANCELLED:
        raise ValidationError(
            "No es posible regenerar una invitacion anulada."
        )

    invitation.token_version += 1
    invitation.save()
    return invitation
