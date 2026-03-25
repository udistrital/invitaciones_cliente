from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from apps.invitations.models import AccessPoint, Invitation, ValidationLog
from apps.invitations.services import rotate_invitation_token


@admin.register(AccessPoint)
class AccessPointAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "ceremony", "is_active")
    list_filter = ("ceremony", "is_active")
    search_fields = ("code", "name", "description")
    ordering = ("ceremony", "name")


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "graduate",
        "sequence_number",
        "status",
        "used_by",
        "used_access_point",
        "sent_at",
        "used_at",
    )
    list_filter = ("status", "graduate__ceremony", "used_access_point")
    search_fields = (
        "public_id__exact",
        "code",
        "graduate__full_name",
        "graduate__document_number",
    )
    readonly_fields = ("public_id", "code")
    ordering = ("-created_at",)
    list_select_related = ("graduate", "graduate__ceremony", "used_by", "used_access_point")
    actions = ("regenerate_selected_invitations",)

    @admin.action(description="Regenerar token de las invitaciones seleccionadas")
    def regenerate_selected_invitations(self, request, queryset):
        regenerated = 0
        skipped = 0
        for invitation in queryset:
            try:
                rotate_invitation_token(invitation)
                regenerated += 1
            except ValidationError:
                skipped += 1
        self.message_user(
            request,
            f"Se regeneraron {regenerated} invitaciones.",
        )
        if skipped:
            self.message_user(
                request,
                (
                    f"Se omitieron {skipped} invitaciones porque ya fueron usadas "
                    "o estan anuladas."
                ),
                level=messages.WARNING,
            )


@admin.register(ValidationLog)
class ValidationLogAdmin(admin.ModelAdmin):
    list_display = (
        "validated_at",
        "result",
        "invitation",
        "validator",
        "access_point",
        "device_label",
        "marked_as_used",
        "source_ip",
    )
    list_filter = ("result", "marked_as_used", "access_point", "validated_at")
    search_fields = (
        "token_fingerprint",
        "invitation__code",
        "invitation__graduate__full_name",
        "validator__username",
        "device_label",
    )
    ordering = ("-validated_at",)
    list_select_related = ("invitation", "validator", "access_point")
