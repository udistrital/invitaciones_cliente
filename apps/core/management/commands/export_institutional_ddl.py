from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone


INSTITUTIONAL_DDL_MIGRATIONS = (
    ("core", "0001_initial"),
    ("ceremonies", "0001_initial"),
    ("accounts", "0001_initial"),
    ("graduates", "0001_initial"),
    ("invitations", "0001_initial"),
)


class Command(BaseCommand):
    help = (
        "Exporta el SQL de las migraciones institucionales al archivo indicado."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default="docs/ddl/invitaciones_grado.sql",
            help="Ruta del archivo SQL a generar.",
        )

    def handle(self, *args, **options):
        output_path = Path(options["output"]).expanduser()
        if not output_path.is_absolute():
            output_path = Path(settings.BASE_DIR) / output_path

        output_path.parent.mkdir(parents=True, exist_ok=True)

        sections: list[str] = [
            "-- DDL institucional generado desde migraciones Django",
            "-- Alcance: esquema invitaciones_grado y tablas propias del dominio",
            f"-- Generado: {timezone.now().isoformat()}",
            "-- Nota: este artefacto asume que las tablas tecnicas de Django",
            "-- (auth_*, django_*, sessions, admin_*) se gestionan aparte.",
            "",
        ]

        for app_label, migration_name in INSTITUTIONAL_DDL_MIGRATIONS:
            buffer = StringIO()
            call_command(
                "sqlmigrate",
                app_label,
                migration_name,
                stdout=buffer,
                no_color=True,
                verbosity=0,
            )
            sql = buffer.getvalue().strip()
            sections.extend(
                [
                    f"-- {app_label}.{migration_name}",
                    sql,
                    "",
                ]
            )

        output_path.write_text("\n".join(sections).rstrip() + "\n", encoding="utf-8")
        self.stdout.write(
            self.style.SUCCESS(f"DDL institucional exportado a {output_path}")
        )
