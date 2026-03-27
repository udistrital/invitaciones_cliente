from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Graduate(TimeStampedModel):
    ceremony = models.ForeignKey(
        "ceremonies.Ceremony",
        on_delete=models.PROTECT,
        related_name="graduates",
        verbose_name="ceremonia",
    )
    document_type = models.CharField("tipo de documento", max_length=20, blank=True)
    student_code = models.CharField("codigo estudiantil", max_length=32, blank=True)
    document_number = models.CharField("documento", max_length=32)
    full_name = models.CharField("nombre completo", max_length=255)
    academic_program = models.CharField("programa academico", max_length=255)
    email = models.EmailField("correo electronico", blank=True)
    invitation_quota = models.PositiveSmallIntegerField(
        "cantidad de invitaciones",
        default=3,
    )

    class Meta:
        ordering = ("full_name",)
        verbose_name = "graduando"
        verbose_name_plural = "graduandos"
        constraints = [
            models.CheckConstraint(
                check=models.Q(invitation_quota__gte=0),
                name="graduate_invitation_quota_gte_0",
            ),
            models.UniqueConstraint(
                fields=("ceremony", "document_number"),
                name="unique_graduate_document_per_ceremony",
            ),
            models.UniqueConstraint(
                fields=("ceremony", "student_code"),
                condition=~models.Q(student_code=""),
                name="unique_graduate_student_code_per_ceremony",
            ),
        ]
        indexes = [
            models.Index(fields=("document_number",), name="graduate_document_idx"),
            models.Index(fields=("student_code",), name="graduate_student_code_idx"),
            models.Index(
                fields=("ceremony", "full_name"),
                name="graduate_ceremony_name_idx",
            ),
        ]

    def __str__(self) -> str:
        return self.full_name


class GraduateImportBatch(TimeStampedModel):
    class Status(models.TextChoices):
        VALIDATED = "validated", "Validado"
        CONFIRMED = "confirmed", "Confirmado"
        FAILED = "failed", "Fallido"

    ceremony = models.ForeignKey(
        "ceremonies.Ceremony",
        on_delete=models.PROTECT,
        related_name="graduate_import_batches",
        verbose_name="ceremonia",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="uploaded_graduate_import_batches",
        verbose_name="cargado por",
        null=True,
        blank=True,
    )
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="confirmed_graduate_import_batches",
        verbose_name="confirmado por",
        null=True,
        blank=True,
    )
    source_filename = models.CharField("archivo fuente", max_length=255)
    file_sha256 = models.CharField("sha256", max_length=64)
    status = models.CharField(
        "estado",
        max_length=20,
        choices=Status.choices,
        default=Status.VALIDATED,
        db_index=True,
    )
    rows_total = models.PositiveIntegerField("filas leidas", default=0)
    rows_valid = models.PositiveIntegerField("filas validas", default=0)
    rows_error = models.PositiveIntegerField("filas con error", default=0)
    graduates_created = models.PositiveIntegerField("graduandos creados", default=0)
    graduates_updated = models.PositiveIntegerField("graduandos actualizados", default=0)
    invitations_created = models.PositiveIntegerField("invitaciones creadas", default=0)
    preview_payload = models.JSONField("resultado de validacion", default=dict, blank=True)
    failure_message = models.TextField("detalle de fallo", blank=True)
    confirmed_at = models.DateTimeField("fecha de confirmacion", null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "lote de importacion de graduandos"
        verbose_name_plural = "lotes de importacion de graduandos"
        indexes = [
            models.Index(
                fields=("ceremony", "status", "created_at"),
                name="gradimp_ceremony_status_idx",
            )
        ]

    def __str__(self) -> str:
        return f"{self.ceremony.code} - {self.source_filename}"
