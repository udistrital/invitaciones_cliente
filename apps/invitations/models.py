import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel


class AccessPoint(TimeStampedModel):
    ceremony = models.ForeignKey(
        "ceremonies.Ceremony",
        on_delete=models.PROTECT,
        related_name="access_points",
        verbose_name="ceremonia",
    )
    code = models.CharField("código", max_length=32)
    name = models.CharField("nombre", max_length=100)
    description = models.CharField("descripción", max_length=255, blank=True)
    is_active = models.BooleanField("activo", default=True)

    class Meta:
        ordering = ("ceremony", "name")
        verbose_name = "punto de acceso"
        verbose_name_plural = "puntos de acceso"
        constraints = [
            models.UniqueConstraint(
                fields=("ceremony", "code"),
                name="unique_access_point_code_per_ceremony",
            )
        ]
        indexes = [
            models.Index(
                fields=("ceremony", "is_active"),
                name="accpt_cer_active_idx",
            )
        ]

    def __str__(self) -> str:
        return f"{self.ceremony.code} - {self.name}"


class Invitation(TimeStampedModel):
    class Status(models.TextChoices):
        CREATED = "created", "Creada"
        SENT = "sent", "Enviada"
        USED = "used", "Usada"
        CANCELLED = "cancelled", "Anulada"

    graduate = models.ForeignKey(
        "graduates.Graduate",
        on_delete=models.PROTECT,
        related_name="invitations",
        verbose_name="graduando",
    )
    public_id = models.UUIDField(
        "identificador público",
        default=uuid.uuid4,
        editable=False,
        unique=True,
    )
    sequence_number = models.PositiveSmallIntegerField("número de invitación")
    code = models.CharField(
        "código",
        max_length=64,
        unique=True,
        editable=False,
    )
    token_version = models.PositiveSmallIntegerField(
        "versión del token",
        default=1,
    )
    status = models.CharField(
        "estado",
        max_length=20,
        choices=Status.choices,
        default=Status.CREATED,
        db_index=True,
    )
    sent_at = models.DateTimeField("fecha de envío", blank=True, null=True)
    used_at = models.DateTimeField("fecha de uso", blank=True, null=True)
    cancelled_at = models.DateTimeField("fecha de anulación", blank=True, null=True)
    used_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="used_invitations",
        verbose_name="validada por",
        null=True,
        blank=True,
    )
    used_access_point = models.ForeignKey(
        "invitations.AccessPoint",
        on_delete=models.SET_NULL,
        related_name="used_invitations",
        verbose_name="punto de acceso",
        null=True,
        blank=True,
    )
    used_device_label = models.CharField(
        "etiqueta del dispositivo",
        max_length=100,
        blank=True,
    )
    used_from_ip = models.GenericIPAddressField(
        "IP de validación exitosa",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "invitación"
        verbose_name_plural = "invitaciones"
        constraints = [
            models.CheckConstraint(
                check=models.Q(sequence_number__gte=1),
                name="invitation_sequence_number_gte_1",
            ),
            models.CheckConstraint(
                check=models.Q(token_version__gte=1),
                name="invitation_token_version_gte_1",
            ),
            models.UniqueConstraint(
                fields=("graduate", "sequence_number"),
                name="unique_invitation_sequence_per_graduate",
            ),
            models.CheckConstraint(
                check=(
                    (
                        Q(status="used")
                        & Q(used_at__isnull=False)
                        & Q(cancelled_at__isnull=True)
                    )
                    | (
                        Q(status="cancelled")
                        & Q(cancelled_at__isnull=False)
                        & Q(used_at__isnull=True)
                    )
                    | (
                        Q(status__in=["created", "sent"])
                        & Q(used_at__isnull=True)
                        & Q(cancelled_at__isnull=True)
                    )
                ),
                name="invitation_status_dates_consistent",
            ),
        ]
        indexes = [
            models.Index(
                fields=("graduate", "status"),
                name="invitation_graduate_status_idx",
            ),
            models.Index(
                fields=("status", "used_at"),
                name="invitation_status_used_at_idx",
            ),
        ]

    def __str__(self) -> str:
        return self.code or str(self.public_id)

    def ensure_code(self) -> None:
        if not self.public_id:
            self.public_id = uuid.uuid4()
        if not self.code:
            self.code = f"INV-{self.public_id.hex[:12].upper()}"

    def clean(self) -> None:
        super().clean()

        if self.graduate_id and self.sequence_number:
            if self.sequence_number > self.graduate.invitation_quota:
                raise ValidationError(
                    {
                        "sequence_number": (
                            "El número de invitación no puede superar "
                            "el cupo configurado para el graduando."
                        )
                    }
                )

        if (
            self.used_access_point_id
            and self.graduate_id
            and self.used_access_point.ceremony_id != self.graduate.ceremony_id
        ):
            raise ValidationError(
                {
                    "used_access_point": (
                        "El punto de acceso debe pertenecer a la misma ceremonia "
                        "de la invitación."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.ensure_code()
        self.full_clean()
        return super().save(*args, **kwargs)


class ValidationLog(models.Model):
    class Result(models.TextChoices):
        VALID = "valid", "Válida"
        USED = "used", "Usada"
        CANCELLED = "cancelled", "Anulada"
        INVALID_TOKEN = "invalid_token", "Token inválido"
        NOT_FOUND = "not_found", "No encontrada"
        ERROR = "error", "Error"

    invitation = models.ForeignKey(
        "invitations.Invitation",
        on_delete=models.SET_NULL,
        related_name="validation_logs",
        verbose_name="invitación",
        null=True,
        blank=True,
    )
    token_fingerprint = models.CharField(
        "huella del token", max_length=16, blank=True, db_index=True
    )
    validator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="invitation_validation_logs",
        verbose_name="validado por",
        null=True,
        blank=True,
    )
    access_point = models.ForeignKey(
        "invitations.AccessPoint",
        on_delete=models.SET_NULL,
        related_name="validation_logs",
        verbose_name="punto de acceso",
        null=True,
        blank=True,
    )
    device_label = models.CharField(
        "etiqueta del dispositivo",
        max_length=100,
        blank=True,
    )
    result = models.CharField(
        "resultado",
        max_length=20,
        choices=Result.choices,
        db_index=True,
    )
    validated_at = models.DateTimeField("fecha de validación", auto_now_add=True)
    marked_as_used = models.BooleanField("marcada como usada", default=False)
    source_ip = models.GenericIPAddressField(
        "dirección IP", null=True, blank=True
    )
    user_agent = models.TextField("user agent", blank=True)

    class Meta:
        ordering = ("-validated_at",)
        verbose_name = "registro de validación"
        verbose_name_plural = "registros de validación"
        constraints = [
            models.CheckConstraint(
                check=Q(marked_as_used=False) | Q(invitation__isnull=False),
                name="validation_log_marked_used_requires_invitation",
            )
        ]
        indexes = [
            models.Index(
                fields=("invitation", "validated_at"),
                name="vlog_inv_time_idx",
            ),
            models.Index(
                fields=("result", "validated_at"),
                name="vlog_result_time_idx",
            ),
            models.Index(
                fields=("validator", "validated_at"),
                name="vlog_user_time_idx",
            ),
            models.Index(
                fields=("access_point", "validated_at"),
                name="vlog_ap_time_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_result_display()} - {self.validated_at:%Y-%m-%d %H:%M:%S}"

    def clean(self) -> None:
        super().clean()

        if self.marked_as_used and not self.invitation_id:
            raise ValidationError(
                {
                    "marked_as_used": (
                        "No es posible marcar una validación como usada "
                        "sin una invitación asociada."
                    )
                }
            )

        if (
            self.access_point_id
            and self.invitation_id
            and self.access_point.ceremony_id != self.invitation.graduate.ceremony_id
        ):
            raise ValidationError(
                {
                    "access_point": (
                        "El punto de acceso debe pertenecer a la misma ceremonia "
                        "de la invitación validada."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
