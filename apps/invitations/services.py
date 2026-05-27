import hashlib
import io
from datetime import timedelta
from dataclasses import dataclass
from urllib.parse import urlencode
from typing import List, Optional

import qrcode
from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from reportlab.lib.pagesizes import A4, A6
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from apps.graduates.models import Graduate
from apps.invitations.models import AccessPoint, Invitation, ValidationLog


INVITATION_TOKEN_SALT = "apps.invitations.token"


class InvalidInvitationToken(Exception):
    def __init__(self, message: str, result: str = ValidationLog.Result.INVALID_TOKEN):
        super().__init__(message)
        self.result = result


@dataclass
class ValidationOutcome:
    state: str
    message: str
    invitation: Optional[Invitation]
    log_result: str
    token_fingerprint: str
    marked_as_used: bool = False


def generate_invitation_token(invitation: Invitation) -> str:
    signer = signing.Signer(salt=INVITATION_TOKEN_SALT)
    payload = {
        "invitation": str(invitation.public_id),
        "version": invitation.token_version,
    }
    return signer.sign_object(payload, compress=False)


def get_token_fingerprint(token: str) -> str:
    if not token:
        return ""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16].upper()


def decode_invitation_token(token: str) -> dict:
    signer = signing.Signer(salt=INVITATION_TOKEN_SALT)

    if not token:
        raise InvalidInvitationToken(
            "No se recibio un token de invitacion.",
            result=ValidationLog.Result.NOT_FOUND,
        )

    try:
        return signer.unsign_object(token)
    except signing.BadSignature as exc:
        raise InvalidInvitationToken("La firma del token no es válida.") from exc


def get_invitation_from_token(token: str) -> Invitation:
    payload = decode_invitation_token(token)

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
        raise InvalidInvitationToken(
            "La invitacion no existe.",
            result=ValidationLog.Result.NOT_FOUND,
        ) from exc

    if invitation.token_version != token_version:
        raise InvalidInvitationToken("El token de la invitación fue reemplazado.")

    return invitation


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

    pdf.drawImage(qr_image, width - 200, height - 300, width=140, height=140)

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


def issue_invitations_for_ceremony(ceremony) -> int:
    generated = 0
    for graduate in ceremony.graduates.all().order_by("full_name"):
        generated += len(issue_invitations_for_graduate(graduate))
    return generated


def rotate_invitation_token(invitation: Invitation) -> Invitation:
    if invitation.status == Invitation.Status.USED:
        raise ValidationError(
            "No es posible regenerar una invitacion que ya fue utilizada."
        )

    if invitation.status == Invitation.Status.CANCELLED:
        raise ValidationError(
            "No es posible regenerar una invitacion anulada."
        )

    invitation.token_version += 1
    invitation.save()
    return invitation


def cancel_invitation(invitation: Invitation) -> Invitation:
    if invitation.status == Invitation.Status.USED:
        raise ValidationError(
            "No es posible anular una invitacion que ya fue utilizada."
        )

    if invitation.status == Invitation.Status.CANCELLED:
        return invitation

    invitation.status = Invitation.Status.CANCELLED
    invitation.cancelled_at = timezone.now()
    invitation.save()
    return invitation


def get_client_ip(request) -> str:
    if getattr(settings, "USE_X_FORWARDED_FOR", False):
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def get_device_label(request) -> str:
    return request.headers.get("X-Device-Label", "")[:100]


def get_validator_user(request):
    user = getattr(request, "user", None)
    if user and user.is_authenticated:
        return user
    return None


def has_staff_session(request) -> bool:
    user = getattr(request, "user", None)
    return bool(user and user.is_authenticated and user.is_staff)


def get_invitation_state(invitation: Invitation) -> str:
    if invitation.status == Invitation.Status.USED:
        return ValidationLog.Result.USED
    if invitation.status == Invitation.Status.CANCELLED:
        return ValidationLog.Result.CANCELLED
    return ValidationLog.Result.VALID


def build_validation_message(state: str, invitation: Optional[Invitation] = None) -> str:
    if state == ValidationLog.Result.VALID:
        return "Invitacion valida para ingreso."
    if state == ValidationLog.Result.USED:
        used_at = invitation.used_at if invitation else None
        if used_at:
            used_at_text = timezone.localtime(used_at).strftime("%d/%m/%Y %I:%M %p")
            return f"Esta invitacion ya fue utilizada el {used_at_text}."
        return "Esta invitacion ya fue utilizada."
    if state == ValidationLog.Result.CANCELLED:
        return "Esta invitacion se encuentra anulada."
    return "La invitacion es inexistente o el QR ya no es valido."


def get_display_state(state: str) -> str:
    if state == ValidationLog.Result.VALID:
        return "valid"
    if state == ValidationLog.Result.USED:
        return "used"
    if state == ValidationLog.Result.CANCELLED:
        return "cancelled"
    return "not_found"


def resolve_access_point(request, ceremony=None, *, allow_session=True):
    access_point_id = request.POST.get("access_point") or request.GET.get("access_point")

    if not access_point_id and allow_session and has_staff_session(request):
        access_point_id = request.session.get("validation_access_point_id")

    if not access_point_id or ceremony is None:
        return None

    try:
        access_point = ceremony.access_points.get(pk=access_point_id, is_active=True)
    except (AccessPoint.DoesNotExist, ValueError, TypeError):
        return None

    return access_point


def persist_validation_context(request, access_point: Optional[AccessPoint]) -> None:
    if access_point is not None and has_staff_session(request):
        request.session["validation_access_point_id"] = access_point.pk


def find_recent_validation_log(
    *,
    token_fingerprint: str,
    invitation: Optional[Invitation],
    validator,
    access_point: Optional[AccessPoint],
    device_label: str,
    result: str,
    marked_as_used: bool,
    source_ip: Optional[str],
):
    dedup_window_seconds = getattr(settings, "VALIDATION_LOG_DEDUP_WINDOW_SECONDS", 0)
    if dedup_window_seconds <= 0 or not token_fingerprint:
        return None

    window_start = timezone.now() - timedelta(seconds=dedup_window_seconds)
    return (
        ValidationLog.objects.filter(
            token_fingerprint=token_fingerprint,
            invitation=invitation,
            validator=validator,
            access_point=access_point,
            device_label=device_label,
            result=result,
            marked_as_used=marked_as_used,
            source_ip=source_ip,
            validated_at__gte=window_start,
        )
        .order_by("-validated_at")
        .first()
    )


def log_validation_attempt(
    *,
    token: str,
    request,
    result: str,
    invitation: Optional[Invitation] = None,
    marked_as_used: bool = False,
    access_point: Optional[AccessPoint] = None,
) -> ValidationLog:
    token_fingerprint = get_token_fingerprint(token)
    validator = get_validator_user(request)
    device_label = get_device_label(request)
    source_ip = get_client_ip(request) or None

    duplicate_log = find_recent_validation_log(
        token_fingerprint=token_fingerprint,
        invitation=invitation,
        validator=validator,
        access_point=access_point,
        device_label=device_label,
        result=result,
        marked_as_used=marked_as_used,
        source_ip=source_ip,
    )
    if duplicate_log is not None:
        return duplicate_log

    return ValidationLog.objects.create(
        invitation=invitation,
        token_fingerprint=token_fingerprint,
        validator=validator,
        access_point=access_point,
        device_label=device_label,
        result=result,
        marked_as_used=marked_as_used,
        source_ip=source_ip,
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )


def inspect_invitation_token(token: str, request) -> ValidationOutcome:
    try:
        invitation = get_invitation_from_token(token)
        access_point = resolve_access_point(request, invitation.graduate.ceremony)
        result = get_invitation_state(invitation)
        log_validation_attempt(
            token=token,
            request=request,
            result=result,
            invitation=invitation,
            access_point=access_point,
        )
        return ValidationOutcome(
            state=get_display_state(result),
            message=build_validation_message(result, invitation),
            invitation=invitation,
            log_result=result,
            token_fingerprint=get_token_fingerprint(token),
        )
    except InvalidInvitationToken as exc:
        log_validation_attempt(
            token=token,
            request=request,
            result=exc.result,
        )
        return ValidationOutcome(
            state="not_found",
            message=build_validation_message(exc.result),
            invitation=None,
            log_result=exc.result,
            token_fingerprint=get_token_fingerprint(token),
        )


def consume_invitation(token: str, request, access_point: Optional[AccessPoint] = None) -> ValidationOutcome:
    try:
        payload = decode_invitation_token(token)
    except InvalidInvitationToken as exc:
        log_validation_attempt(
            token=token,
            request=request,
            result=exc.result,
        )
        return ValidationOutcome(
            state="not_found",
            message=build_validation_message(exc.result),
            invitation=None,
            log_result=exc.result,
            token_fingerprint=get_token_fingerprint(token),
        )

    public_id = payload.get("invitation")
    token_version = payload.get("version")

    try:
        with transaction.atomic():
            invitation = (
                Invitation.objects.select_for_update()
                .select_related("graduate", "graduate__ceremony")
                .get(public_id=public_id)
            )

            if invitation.token_version != token_version:
                raise InvalidInvitationToken(
                    "El token de la invitacion fue reemplazado."
                )

            if access_point is None:
                access_point = resolve_access_point(
                    request,
                    invitation.graduate.ceremony,
                    allow_session=True,
                )

            state_result = get_invitation_state(invitation)

            if state_result == ValidationLog.Result.VALID:
                invitation.status = Invitation.Status.USED
                invitation.used_at = timezone.now()
                invitation.used_by = get_validator_user(request)
                invitation.used_access_point = access_point
                invitation.used_device_label = get_device_label(request)
                invitation.used_from_ip = get_client_ip(request) or None
                invitation.save()
                persist_validation_context(request, access_point)
                log_validation_attempt(
                    token=token,
                    request=request,
                    result=ValidationLog.Result.VALID,
                    invitation=invitation,
                    marked_as_used=True,
                    access_point=access_point,
                )
                return ValidationOutcome(
                    state="used",
                    message="Invitacion marcada como usada correctamente.",
                    invitation=invitation,
                    log_result=ValidationLog.Result.VALID,
                    token_fingerprint=get_token_fingerprint(token),
                    marked_as_used=True,
                )

            log_validation_attempt(
                token=token,
                request=request,
                result=state_result,
                invitation=invitation,
                access_point=access_point,
            )
            return ValidationOutcome(
                state=get_display_state(state_result),
                message=build_validation_message(state_result, invitation),
                invitation=invitation,
                log_result=state_result,
                token_fingerprint=get_token_fingerprint(token),
            )
    except Invitation.DoesNotExist:
        log_validation_attempt(
            token=token,
            request=request,
            result=ValidationLog.Result.NOT_FOUND,
        )
        return ValidationOutcome(
            state="not_found",
            message=build_validation_message(ValidationLog.Result.NOT_FOUND),
            invitation=None,
            log_result=ValidationLog.Result.NOT_FOUND,
            token_fingerprint=get_token_fingerprint(token),
        )
    except InvalidInvitationToken as exc:
        log_validation_attempt(
            token=token,
            request=request,
            result=exc.result,
        )
        return ValidationOutcome(
            state="not_found",
            message=build_validation_message(exc.result),
            invitation=None,
            log_result=exc.result,
            token_fingerprint=get_token_fingerprint(token),
        )
