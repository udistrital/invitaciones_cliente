import uuid

from django.db import models

from apps.core.models import TimeStampedModel


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
    code = models.CharField("código", max_length=64, unique=True, blank=True, null=True)
    token_hash = models.CharField(
        "hash del token",
        max_length=64,
        unique=True,
        blank=True,
        null=True,
        db_index=True,
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

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "invitación"
        verbose_name_plural = "invitaciones"

    def __str__(self) -> str:
        return self.code or str(self.public_id)


class ValidationLog(models.Model):
    class Result(models.TextChoices):
        VALID = "valid", "Válida"
        USED = "used", "Usada"
        CANCELLED = "cancelled", "Anulada"
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
        "huella del token", max_length=16, blank=True
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

    def __str__(self) -> str:
        return f"{self.get_result_display()} - {self.validated_at:%Y-%m-%d %H:%M:%S}"
