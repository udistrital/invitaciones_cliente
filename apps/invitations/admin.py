from django.contrib import admin

from apps.invitations.models import Invitation, ValidationLog


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ("public_id", "graduate", "status", "code", "sent_at", "used_at")
    list_filter = ("status", "graduate__ceremony")
    search_fields = (
        "public_id__exact",
        "code",
        "graduate__full_name",
        "graduate__document_number",
    )
    readonly_fields = ("public_id",)
    ordering = ("-created_at",)


@admin.register(ValidationLog)
class ValidationLogAdmin(admin.ModelAdmin):
    list_display = (
        "validated_at",
        "result",
        "invitation",
        "marked_as_used",
        "source_ip",
    )
    list_filter = ("result", "marked_as_used", "validated_at")
    search_fields = (
        "token_fingerprint",
        "invitation__code",
        "invitation__graduate__full_name",
    )
    ordering = ("-validated_at",)
