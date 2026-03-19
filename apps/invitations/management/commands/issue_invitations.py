from django.core.management.base import BaseCommand, CommandError

from apps.ceremonies.models import Ceremony
from apps.graduates.models import Graduate
from apps.invitations.services import (
    build_download_url,
    build_validation_url,
    issue_invitations_for_graduate,
)


class Command(BaseCommand):
    help = "Genera las invitaciones faltantes para un graduando o una ceremonia."

    def add_arguments(self, parser):
        parser.add_argument("--graduate-id", type=int)
        parser.add_argument("--ceremony-code", type=str)

    def handle(self, *args, **options):
        graduate_id = options.get("graduate_id")
        ceremony_code = options.get("ceremony_code")

        if not graduate_id and not ceremony_code:
            raise CommandError(
                "Debes indicar --graduate-id o --ceremony-code."
            )

        if graduate_id and ceremony_code:
            raise CommandError(
                "Usa solo una opcion: --graduate-id o --ceremony-code."
            )

        try:
            if graduate_id:
                graduates = [Graduate.objects.get(pk=graduate_id)]
            else:
                ceremony = Ceremony.objects.get(code=ceremony_code)
                graduates = list(ceremony.graduates.all().order_by("full_name"))
        except Graduate.DoesNotExist as exc:
            raise CommandError("No existe el graduando indicado.") from exc
        except Ceremony.DoesNotExist as exc:
            raise CommandError("No existe la ceremonia indicada.") from exc

        for graduate in graduates:
            invitations = issue_invitations_for_graduate(graduate)
            self.stdout.write(
                self.style.SUCCESS(
                    f"{graduate.full_name}: {len(invitations)} invitaciones listas."
                )
            )
            for invitation in invitations:
                self.stdout.write(
                    f"- {invitation.code} | validar: {build_validation_url(invitation)}"
                )
                self.stdout.write(
                    f"  descargar: {build_download_url(invitation)}"
                )
