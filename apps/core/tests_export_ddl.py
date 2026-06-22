from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import TestCase

from apps.core.schema import INSTITUTIONAL_SCHEMA


class ExportInstitutionalDDLCommandTest(TestCase):
    def test_export_command_writes_expected_sql(self):
        with TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "invitaciones_grado.sql"

            call_command("export_institutional_ddl", output=str(output_path))

            sql = output_path.read_text(encoding="utf-8")

        self.assertIn(
            f'CREATE SCHEMA IF NOT EXISTS "{INSTITUTIONAL_SCHEMA}";',
            sql,
        )
        self.assertIn(
            f"SET search_path TO {INSTITUTIONAL_SCHEMA}, public;",
            sql,
        )
        self.assertIn(
            f'CREATE TABLE "{INSTITUTIONAL_SCHEMA}"."auth_user"',
            sql,
        )
        self.assertIn(
            f'CREATE TABLE "{INSTITUTIONAL_SCHEMA}"."django_session"',
            sql,
        )
        self.assertIn(
            f'CREATE TABLE IF NOT EXISTS "{INSTITUTIONAL_SCHEMA}"."django_migrations"',
            sql,
        )
        self.assertIn(f'CREATE TABLE "{INSTITUTIONAL_SCHEMA}"."ceremonia"', sql)
        self.assertIn(f'CREATE TABLE "{INSTITUTIONAL_SCHEMA}"."graduando"', sql)
        self.assertIn(f'CREATE TABLE "{INSTITUTIONAL_SCHEMA}"."invitacion"', sql)
        self.assertIn(
            f'INSERT INTO "{INSTITUTIONAL_SCHEMA}"."django_content_type"',
            sql,
        )
        self.assertIn(
            f'INSERT INTO "{INSTITUTIONAL_SCHEMA}"."auth_permission"',
            sql,
        )
        self.assertIn(
            f'REFERENCES "{INSTITUTIONAL_SCHEMA}"."auth_user"',
            sql,
        )
        self.assertNotIn('CREATE TABLE "auth_user"', sql)
