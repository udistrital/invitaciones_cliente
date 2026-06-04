from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import TestCase


class ExportInstitutionalDDLCommandTest(TestCase):
    def test_export_command_writes_expected_sql(self):
        with TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "invitaciones_grado.sql"

            call_command("export_institutional_ddl", output=str(output_path))

            sql = output_path.read_text(encoding="utf-8")

        self.assertIn('CREATE SCHEMA IF NOT EXISTS "invitaciones_grado";', sql)
        self.assertIn('CREATE TABLE "invitaciones_grado"."ceremonia"', sql)
        self.assertIn('CREATE TABLE "invitaciones_grado"."graduando"', sql)
        self.assertIn('CREATE TABLE "invitaciones_grado"."invitacion"', sql)
        self.assertIn('REFERENCES "auth_user"', sql)
