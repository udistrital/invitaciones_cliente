from django.db import models

from apps.core.models import TimeStampedModel, schema_table


class Ceremony(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        SCHEDULED = "scheduled", "Programada"
        CLOSED = "closed", "Cerrada"
        CANCELLED = "cancelled", "Cancelada"

    code = models.CharField("codigo", max_length=32, db_column="codigo")
    name = models.CharField("nombre", max_length=255, db_column="nombre")
    scheduled_at = models.DateTimeField(
        "fecha y hora",
        db_column="fecha_programada",
    )
    venue = models.CharField("lugar", max_length=255, db_column="lugar")
    status = models.CharField(
        "estado",
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_column="estado",
    )

    class Meta:
        db_table = schema_table("ceremonia")
        ordering = ("scheduled_at", "name")
        verbose_name = "ceremonia"
        verbose_name_plural = "ceremonias"
        constraints = [
            models.UniqueConstraint(
                fields=("code",),
                name="uq_ceremonia_codigo",
            ),
        ]
        indexes = [
            models.Index(
                fields=("status", "scheduled_at"),
                name="idx_ceremonia_est_fprog",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"
