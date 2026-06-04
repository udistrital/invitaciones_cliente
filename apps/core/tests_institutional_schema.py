from django.db import connection
from django.test import TestCase

from apps.accounts.models import ExternalIdentity
from apps.ceremonies.models import Ceremony
from apps.graduates.models import Graduate, GraduateImportBatch
from apps.invitations.models import AccessPoint, Invitation, ValidationLog


INSTITUTIONAL_SCHEMA = "invitaciones_grado"


class InstitutionalSchemaTest(TestCase):
    def test_models_map_to_institutional_schema(self):
        expected_tables = {
            Ceremony: '"invitaciones_grado"."ceremonia"',
            Graduate: '"invitaciones_grado"."graduando"',
            GraduateImportBatch: '"invitaciones_grado"."lote_importacion_graduando"',
            AccessPoint: '"invitaciones_grado"."punto_acceso"',
            Invitation: '"invitaciones_grado"."invitacion"',
            ValidationLog: '"invitaciones_grado"."registro_validacion"',
            ExternalIdentity: '"invitaciones_grado"."identidad_externa"',
        }

        for model, table_name in expected_tables.items():
            self.assertEqual(model._meta.db_table, table_name)
            self.assertEqual(model._meta.pk.get_internal_type(), "AutoField")

        self.assertEqual(Ceremony._meta.get_field("code").db_column, "codigo")
        self.assertEqual(
            Graduate._meta.get_field("document_number").db_column,
            "numero_documento",
        )
        self.assertEqual(
            Invitation._meta.get_field("public_id").db_column,
            "identificador_publico",
        )
        self.assertEqual(
            ValidationLog._meta.get_field("source_ip").db_column,
            "direccion_ip",
        )

    def test_tables_exist_in_institutional_schema(self):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = %s
                ORDER BY table_name
                """,
                [INSTITUTIONAL_SCHEMA],
            )
            table_names = {row[0] for row in cursor.fetchall()}

        self.assertTrue(
            {
                "ceremonia",
                "graduando",
                "lote_importacion_graduando",
                "punto_acceso",
                "invitacion",
                "registro_validacion",
                "identidad_externa",
            }.issubset(table_names)
        )

    def test_common_columns_exist_in_all_scope_tables(self):
        expected_tables = [
            "ceremonia",
            "graduando",
            "lote_importacion_graduando",
            "punto_acceso",
            "invitacion",
            "registro_validacion",
            "identidad_externa",
        ]

        for table_name in expected_tables:
            with self.subTest(table=table_name):
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = %s AND table_name = %s
                        """,
                        [INSTITUTIONAL_SCHEMA, table_name],
                    )
                    columns = {row[0] for row in cursor.fetchall()}

                self.assertIn("activo", columns)
                self.assertIn("fecha_creacion", columns)
                self.assertIn("fecha_modificacion", columns)

    def test_auth_tables_remain_outside_institutional_schema(self):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT table_schema
                FROM information_schema.tables
                WHERE table_name = 'auth_user'
                ORDER BY table_schema
                LIMIT 1
                """
            )
            row = cursor.fetchone()

        self.assertIsNotNone(row)
        self.assertNotEqual(row[0], INSTITUTIONAL_SCHEMA)
