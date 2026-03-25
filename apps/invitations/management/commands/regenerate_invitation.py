from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.invitations.models import Invitation
from apps.invitations.services import (
    build_download_url,
    build_validation_url,
    rotate_invitation_token,
)


class Command(BaseCommand):
    help = "Regenera el token de una invitacion existente."

    def add_arguments(self, parser):
        parser.add_argument("--code", required=True, type=str)

    def handle(self, *args, **options):
        try:
            invitation = Invitation.objects.get(code=options["code"])
        except Invitation.DoesNotExist as exc:
            raise CommandError("No existe una invitacion con ese codigo.") from exc

        try:
            rotate_invitation_token(invitation)
        except ValidationError as exc:
            raise CommandError(getattr(exc, "message", str(exc))) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Invitacion {invitation.code} regenerada. Nueva version: {invitation.token_version}"
            )
        )
        self.stdout.write(f"validar: {build_validation_url(invitation)}")
        self.stdout.write(f"descargar: {build_download_url(invitation)}")
