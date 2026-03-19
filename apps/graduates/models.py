from django.db import models

from apps.core.models import TimeStampedModel


class Graduate(TimeStampedModel):
    ceremony = models.ForeignKey(
        "ceremonies.Ceremony",
        on_delete=models.PROTECT,
        related_name="graduates",
        verbose_name="ceremonia",
    )
    student_code = models.CharField("código estudiantil", max_length=32, blank=True)
    document_number = models.CharField("documento", max_length=32)
    full_name = models.CharField("nombre completo", max_length=255)
    email = models.EmailField("correo electrónico", blank=True)
    invitation_quota = models.PositiveSmallIntegerField(
        "cantidad de invitaciones", default=2
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
        ]
        indexes = [
            models.Index(fields=("document_number",), name="graduate_document_idx"),
            models.Index(
                fields=("ceremony", "full_name"),
                name="graduate_ceremony_name_idx",
            ),
        ]

    def __str__(self) -> str:
        return self.full_name
