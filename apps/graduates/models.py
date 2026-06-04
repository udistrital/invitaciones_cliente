from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel, schema_table


class Graduate(TimeStampedModel):
    ceremony = models.ForeignKey(
        "ceremonies.Ceremony",
        on_delete=models.PROTECT,
        related_name="graduates",
        verbose_name="ceremonia",
        db_column="ceremonia_id",
    )
    document_type = models.CharField(
        "tipo de documento",
        max_length=20,
        blank=True,
        db_column="tipo_documento",
    )
    student_code = models.CharField(
        "codigo estudiantil",
        max_length=32,
        blank=True,
        db_column="codigo_estudiantil",
    )
    document_number = models.CharField(
        "documento",
        max_length=32,
        db_column="numero_documento",
    )
    full_name = models.CharField(
        "nombre completo",
        max_length=255,
        db_column="nombre_completo",
    )
    academic_program = models.CharField(
        "programa academico",
        max_length=255,
        db_column="programa_academico",
    )
    email = models.EmailField(
        "correo electronico",
        blank=True,
        db_column="correo_electronico",
    )
    invitation_quota = models.PositiveSmallIntegerField(
        "cantidad de invitaciones",
        default=3,
        db_column="cantidad_invitaciones",
    )

    class Meta:
        db_table = schema_table("graduando")
        ordering = ("full_name",)
        verbose_name = "graduando"
        verbose_name_plural = "graduandos"
        constraints = [
            models.CheckConstraint(
                check=models.Q(invitation_quota__gte=0),
                name="ck_graduando_cant_inv",
            ),
            models.UniqueConstraint(
                fields=("ceremony", "document_number"),
                name="uq_grad_cer_numdoc",
            ),
            models.UniqueConstraint(
                fields=("ceremony", "student_code"),
                condition=~models.Q(student_code=""),
                name="uq_grad_cer_codest",
            ),
        ]
        indexes = [
            models.Index(
                fields=("document_number",),
                name="idx_grad_numdoc",
            ),
            models.Index(
                fields=("student_code",),
                name="idx_grad_codest",
            ),
            models.Index(
                fields=("ceremony", "full_name"),
                name="idx_grad_cer_nom",
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
        db_column="ceremonia_id",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="uploaded_graduate_import_batches",
        verbose_name="cargado por",
        null=True,
        blank=True,
        db_column="usuario_cargue_id",
    )
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="confirmed_graduate_import_batches",
        verbose_name="confirmado por",
        null=True,
        blank=True,
        db_column="usuario_confirmacion_id",
    )
    source_filename = models.CharField(
        "archivo fuente",
        max_length=255,
        db_column="archivo_fuente",
    )
    file_sha256 = models.CharField(
        "sha256",
        max_length=64,
        db_column="archivo_sha256",
    )
    status = models.CharField(
        "estado",
        max_length=20,
        choices=Status.choices,
        default=Status.VALIDATED,
        db_column="estado",
    )
    rows_total = models.PositiveIntegerField(
        "filas leidas",
        default=0,
        db_column="filas_leidas",
    )
    rows_valid = models.PositiveIntegerField(
        "filas validas",
        default=0,
        db_column="filas_validas",
    )
    rows_error = models.PositiveIntegerField(
        "filas con error",
        default=0,
        db_column="filas_error",
    )
    graduates_created = models.PositiveIntegerField(
        "graduandos creados",
        default=0,
        db_column="graduandos_creados",
    )
    graduates_updated = models.PositiveIntegerField(
        "graduandos actualizados",
        default=0,
        db_column="graduandos_actualizados",
    )
    invitations_created = models.PositiveIntegerField(
        "invitaciones creadas",
        default=0,
        db_column="invitaciones_creadas",
    )
    preview_payload = models.JSONField(
        "resultado de validacion",
        default=dict,
        blank=True,
        db_column="resultado_validacion",
    )
    failure_message = models.TextField(
        "detalle de fallo",
        blank=True,
        db_column="detalle_fallo",
    )
    confirmed_at = models.DateTimeField(
        "fecha de confirmacion",
        null=True,
        blank=True,
        db_column="fecha_confirmacion",
    )

    class Meta:
        db_table = schema_table("lote_importacion_graduando")
        ordering = ("-created_at",)
        verbose_name = "lote de importacion de graduandos"
        verbose_name_plural = "lotes de importacion de graduandos"
        indexes = [
            models.Index(
                fields=("ceremony", "status", "created_at"),
                name="idx_limp_cer_est_fcre",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.ceremony.code} - {self.source_filename}"
