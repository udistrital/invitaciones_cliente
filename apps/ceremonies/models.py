from django.db import models

from apps.core.models import TimeStampedModel


class Ceremony(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        SCHEDULED = "scheduled", "Programada"
        CLOSED = "closed", "Cerrada"
        CANCELLED = "cancelled", "Cancelada"

    code = models.CharField("código", max_length=32, unique=True)
    name = models.CharField("nombre", max_length=255)
    scheduled_at = models.DateTimeField("fecha y hora")
    venue = models.CharField("lugar", max_length=255)
    status = models.CharField(
        "estado",
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    class Meta:
        ordering = ("scheduled_at", "name")
        verbose_name = "ceremonia"
        verbose_name_plural = "ceremonias"

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"
