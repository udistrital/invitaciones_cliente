import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel, schema_table


class AccessPoint(TimeStampedModel):
    ceremony = models.ForeignKey(
        "ceremonies.Ceremony",
        on_delete=models.PROTECT,
        related_name="access_points",
        verbose_name="ceremonia",
        db_column="ceremonia_id",
    )
    code = models.CharField("codigo", max_length=32, db_column="codigo")
    name = models.CharField("nombre", max_length=100, db_column="nombre")
    description = models.CharField(
        "descripcion",
        max_length=255,
        blank=True,
        db_column="descripcion",
    )

    class Meta:
        db_table = schema_table("punto_acceso")
        ordering = ("ceremony", "name")
        verbose_name = "punto de acceso"
        verbose_name_plural = "puntos de acceso"
        constraints = [
            models.UniqueConstraint(
                fields=("ceremony", "code"),
                name="uq_ptacc_cer_codigo",
            ),
        ]
        indexes = [
            models.Index(
                fields=("ceremony", "is_active"),
                name="idx_ptacc_cer_act",
            ),
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
        db_column="graduando_id",
    )
    public_id = models.UUIDField(
        "identificador publico",
        default=uuid.uuid4,
        editable=False,
        db_column="identificador_publico",
    )
    sequence_number = models.PositiveSmallIntegerField(
        "numero de invitacion",
        db_column="numero_invitacion",
    )
    code = models.CharField(
        "codigo",
        max_length=64,
        editable=False,
        db_column="codigo",
    )
    token_version = models.PositiveSmallIntegerField(
        "version del token",
        default=1,
        db_column="version_token",
    )
    status = models.CharField(
        "estado",
        max_length=20,
        choices=Status.choices,
        default=Status.CREATED,
        db_column="estado",
    )
    sent_at = models.DateTimeField(
        "fecha de envio",
        blank=True,
        null=True,
        db_column="fecha_envio",
    )
    used_at = models.DateTimeField(
        "fecha de uso",
        blank=True,
        null=True,
        db_column="fecha_uso",
    )
    cancelled_at = models.DateTimeField(
        "fecha de anulacion",
        blank=True,
        null=True,
        db_column="fecha_anulacion",
    )
    used_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="used_invitations",
        verbose_name="validada por",
        null=True,
        blank=True,
        db_column="usuario_validador_id",
    )
    used_access_point = models.ForeignKey(
        "invitations.AccessPoint",
        on_delete=models.SET_NULL,
        related_name="used_invitations",
        verbose_name="punto de acceso",
        null=True,
        blank=True,
        db_column="punto_acceso_uso_id",
    )
    used_device_label = models.CharField(
        "etiqueta del dispositivo",
        max_length=100,
        blank=True,
        db_column="etiqueta_dispositivo_uso",
    )
    used_from_ip = models.GenericIPAddressField(
        "IP de validacion exitosa",
        null=True,
        blank=True,
        db_column="ip_validacion_exitosa",
    )

    class Meta:
        db_table = schema_table("invitacion")
        ordering = ("-created_at",)
        verbose_name = "invitacion"
        verbose_name_plural = "invitaciones"
        constraints = [
            models.CheckConstraint(
                check=models.Q(sequence_number__gte=1),
                name="ck_inv_numero",
            ),
            models.CheckConstraint(
                check=models.Q(token_version__gte=1),
                name="ck_inv_version",
            ),
            models.UniqueConstraint(
                fields=("public_id",),
                name="uq_inv_pubid",
            ),
            models.UniqueConstraint(
                fields=("code",),
                name="uq_inv_codigo",
            ),
            models.UniqueConstraint(
                fields=("graduate", "sequence_number"),
                name="uq_inv_grad_num",
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
                name="ck_inv_estado_fech",
            ),
        ]
        indexes = [
            models.Index(
                fields=("graduate", "status"),
                name="idx_inv_grad_est",
            ),
            models.Index(
                fields=("status", "used_at"),
                name="idx_inv_est_fuso",
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
                            "El numero de invitacion no puede superar "
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
                        "de la invitacion."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.ensure_code()
        self.full_clean()
        return super().save(*args, **kwargs)


class ValidationLog(TimeStampedModel):
    class Result(models.TextChoices):
        VALID = "valid", "Valida"
        USED = "used", "Usada"
        CANCELLED = "cancelled", "Anulada"
        INVALID_TOKEN = "invalid_token", "Token invalido"
        NOT_FOUND = "not_found", "No encontrada"
        ERROR = "error", "Error"

    invitation = models.ForeignKey(
        "invitations.Invitation",
        on_delete=models.SET_NULL,
        related_name="validation_logs",
        verbose_name="invitacion",
        null=True,
        blank=True,
        db_column="invitacion_id",
    )
    token_fingerprint = models.CharField(
        "huella del token",
        max_length=16,
        blank=True,
        db_column="huella_token",
    )
    validator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="invitation_validation_logs",
        verbose_name="validado por",
        null=True,
        blank=True,
        db_column="usuario_validador_id",
    )
    access_point = models.ForeignKey(
        "invitations.AccessPoint",
        on_delete=models.SET_NULL,
        related_name="validation_logs",
        verbose_name="punto de acceso",
        null=True,
        blank=True,
        db_column="punto_acceso_id",
    )
    device_label = models.CharField(
        "etiqueta del dispositivo",
        max_length=100,
        blank=True,
        db_column="etiqueta_dispositivo",
    )
    result = models.CharField(
        "resultado",
        max_length=20,
        choices=Result.choices,
        db_column="resultado",
    )
    validated_at = models.DateTimeField(
        "fecha de validacion",
        auto_now_add=True,
        db_column="fecha_validacion",
    )
    marked_as_used = models.BooleanField(
        "marcada como usada",
        default=False,
        db_column="marcada_como_usada",
    )
    source_ip = models.GenericIPAddressField(
        "direccion IP",
        null=True,
        blank=True,
        db_column="direccion_ip",
    )
    user_agent = models.TextField(
        "user agent",
        blank=True,
        db_column="agente_usuario",
    )

    class Meta:
        db_table = schema_table("registro_validacion")
        ordering = ("-validated_at",)
        verbose_name = "registro de validacion"
        verbose_name_plural = "registros de validacion"
        constraints = [
            models.CheckConstraint(
                check=Q(marked_as_used=False) | Q(invitation__isnull=False),
                name="ck_vlog_uso_req_inv",
            ),
        ]
        indexes = [
            models.Index(
                fields=("token_fingerprint",),
                name="idx_vlog_huella",
            ),
            models.Index(
                fields=("invitation", "validated_at"),
                name="idx_vlog_inv_fval",
            ),
            models.Index(
                fields=("result", "validated_at"),
                name="idx_vlog_res_fval",
            ),
            models.Index(
                fields=("validator", "validated_at"),
                name="idx_vlog_usr_fval",
            ),
            models.Index(
                fields=("access_point", "validated_at"),
                name="idx_vlog_pacc_fval",
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
                        "No es posible marcar una validacion como usada "
                        "sin una invitacion asociada."
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
                        "de la invitacion validada."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
