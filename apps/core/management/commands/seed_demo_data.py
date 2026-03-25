from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.ceremonies.models import Ceremony
from apps.graduates.models import Graduate
from apps.invitations.models import AccessPoint
from apps.invitations.services import issue_invitations_for_ceremony


class Command(BaseCommand):
    help = "Carga datos demo minimos para revisar el flujo funcional local."

    def handle(self, *args, **options):
        ceremony, ceremony_created = Ceremony.objects.get_or_create(
            code="DEMO-2026-01",
            defaults={
                "name": "Ceremonia Demo Institucional",
                "scheduled_at": timezone.now(),
                "venue": "Auditorio Principal",
                "status": Ceremony.Status.SCHEDULED,
            },
        )

        access_points = [
            ("NORTE", "Ingreso norte"),
            ("SUR", "Ingreso sur"),
        ]
        created_access_points = 0
        for code, name in access_points:
            _, created = AccessPoint.objects.get_or_create(
                ceremony=ceremony,
                code=code,
                defaults={"name": name, "is_active": True},
            )
            created_access_points += int(created)

        graduates = [
            {
                "document_number": "10000001",
                "student_code": "20261001",
                "full_name": "Laura Perez",
                "academic_program": "Ingenieria de Sistemas",
                "email": "laura.perez@example.com",
                "invitation_quota": 2,
            },
            {
                "document_number": "10000002",
                "student_code": "20261002",
                "full_name": "Carlos Ruiz",
                "academic_program": "Ingenieria Industrial",
                "email": "carlos.ruiz@example.com",
                "invitation_quota": 2,
            },
        ]

        created_graduates = 0
        for graduate_data in graduates:
            _, created = Graduate.objects.get_or_create(
                ceremony=ceremony,
                document_number=graduate_data["document_number"],
                defaults=graduate_data,
            )
            created_graduates += int(created)

        invitations_total = issue_invitations_for_ceremony(ceremony)

        self.stdout.write(
            self.style.SUCCESS(
                (
                    f"Ceremonia demo lista: {ceremony.code} | creada: {ceremony_created}. "
                    f"Puntos de acceso nuevos: {created_access_points}. "
                    f"Graduandos nuevos: {created_graduates}. "
                    f"Invitaciones disponibles: {invitations_total}."
                )
            )
        )
        self.stdout.write("Backoffice: /gestion/")
        self.stdout.write("Admin Django: /admin/")
