from django.contrib import admin

from apps.accounts.models import ExternalIdentity


@admin.register(ExternalIdentity)
class ExternalIdentityAdmin(admin.ModelAdmin):
    list_display = (
        "provider",
        "issuer",
        "subject",
        "user",
        "email",
        "last_login_at",
    )
    list_filter = ("provider",)
    search_fields = ("subject", "issuer", "email", "user__username", "user__email")
    ordering = ("provider", "issuer", "subject")
