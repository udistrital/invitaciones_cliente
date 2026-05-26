from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class ExternalIdentity(TimeStampedModel):
    class Provider(models.TextChoices):
        WSO2 = "wso2", "WSO2"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="external_identities",
        verbose_name="usuario",
    )
    provider = models.CharField(
        "proveedor",
        max_length=20,
        choices=Provider.choices,
    )
    issuer = models.CharField("issuer", max_length=255)
    subject = models.CharField("subject", max_length=255)
    email = models.EmailField("correo electronico", blank=True)
    username_claim = models.CharField("claim de usuario", max_length=255, blank=True)
    claims_snapshot = models.JSONField("snapshot de claims", default=dict, blank=True)
    last_login_at = models.DateTimeField("ultimo login", null=True, blank=True)

    class Meta:
        verbose_name = "identidad externa"
        verbose_name_plural = "identidades externas"
        ordering = ("provider", "issuer", "subject")
        constraints = [
            models.UniqueConstraint(
                fields=("provider", "issuer", "subject"),
                name="unique_external_identity_provider_issuer_subject",
            )
        ]
        indexes = [
            models.Index(
                fields=("provider", "email"),
                name="extid_provider_email_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.provider}:{self.subject}"
