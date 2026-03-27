from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.ceremonies.models import Ceremony
from apps.graduates.models import Graduate


class GraduateModelTest(TestCase):
    def setUp(self):
        self.ceremony = Ceremony.objects.create(
            code="GRADOS-2026-01",
            name="Ceremonia Central",
            scheduled_at=timezone.now(),
            venue="Auditorio Sabio Caldas",
        )

    def test_duplicate_document_number_in_same_ceremony_fails(self):
        Graduate.objects.create(
            ceremony=self.ceremony,
            document_number="12345678",
            full_name="Laura Perez",
            academic_program="Ingenieria de Sistemas",
            invitation_quota=3,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Graduate.objects.create(
                    ceremony=self.ceremony,
                    document_number="12345678",
                    full_name="Laura Perez Duplicada",
                    academic_program="Ingenieria de Sistemas",
                    invitation_quota=1,
                )

    def test_duplicate_student_code_in_same_ceremony_fails(self):
        Graduate.objects.create(
            ceremony=self.ceremony,
            student_code="20260001",
            document_number="12345678",
            full_name="Laura Perez",
            academic_program="Ingenieria de Sistemas",
            invitation_quota=3,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Graduate.objects.create(
                    ceremony=self.ceremony,
                    student_code="20260001",
                    document_number="87654321",
                    full_name="Carlos Ruiz",
                    academic_program="Ingenieria Industrial",
                    invitation_quota=3,
                )

    def test_same_document_number_is_allowed_in_different_ceremonies(self):
        other_ceremony = Ceremony.objects.create(
            code="GRADOS-2026-02",
            name="Ceremonia Norte",
            scheduled_at=timezone.now(),
            venue="Auditorio Norte",
        )

        Graduate.objects.create(
            ceremony=self.ceremony,
            document_number="12345678",
            full_name="Laura Perez",
            academic_program="Ingenieria de Sistemas",
            invitation_quota=3,
        )
        graduate = Graduate.objects.create(
            ceremony=other_ceremony,
            document_number="12345678",
            full_name="Laura Perez Segunda Ceremonia",
            academic_program="Ingenieria Industrial",
            invitation_quota=1,
        )

        self.assertEqual(graduate.ceremony, other_ceremony)

    def test_default_invitation_quota_is_three(self):
        graduate = Graduate.objects.create(
            ceremony=self.ceremony,
            document_number="10000001",
            full_name="Maria Fernanda",
            academic_program="Matematicas",
        )

        self.assertEqual(graduate.invitation_quota, 3)

    def test_negative_invitation_quota_is_rejected(self):
        graduate = Graduate(
            ceremony=self.ceremony,
            document_number="99999999",
            full_name="Invalido",
            academic_program="Programa de prueba",
            invitation_quota=-1,
        )

        with self.assertRaises(ValidationError):
            graduate.full_clean()
