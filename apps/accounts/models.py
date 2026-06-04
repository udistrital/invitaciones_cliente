from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel, schema_table


class ExternalIdentity(TimeStampedModel):
    class Provider(models.TextChoices):
        WSO2 = "wso2", "WSO2"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="external_identities",
        verbose_name="usuario",
        db_column="usuario_id",
    )
    provider = models.CharField(
        "proveedor",
        max_length=20,
        choices=Provider.choices,
        db_column="proveedor",
    )
    issuer = models.CharField("issuer", max_length=255, db_column="issuer")
    subject = models.CharField("subject", max_length=255, db_column="subject")
    email = models.EmailField(
        "correo electronico",
        blank=True,
        db_column="correo_electronico",
    )
    username_claim = models.CharField(
        "claim de usuario",
        max_length=255,
        blank=True,
        db_column="claim_usuario",
    )
    claims_snapshot = models.JSONField(
        "snapshot de claims",
        default=dict,
        blank=True,
        db_column="snapshot_claims",
    )
    last_login_at = models.DateTimeField(
        "ultimo login",
        null=True,
        blank=True,
        db_column="fecha_ultimo_inicio_sesion",
    )

    class Meta:
        db_table = schema_table("identidad_externa")
        verbose_name = "identidad externa"
        verbose_name_plural = "identidades externas"
        ordering = ("provider", "issuer", "subject")
        constraints = [
            models.UniqueConstraint(
                fields=("provider", "issuer", "subject"),
                name="uq_extid_prov_iss_sub",
            ),
        ]
        indexes = [
            models.Index(
                fields=("provider", "email"),
                name="idx_extid_prov_email",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.provider}:{self.subject}"
