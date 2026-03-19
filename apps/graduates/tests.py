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
            invitation_quota=2,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Graduate.objects.create(
                    ceremony=self.ceremony,
                    document_number="12345678",
                    full_name="Laura Perez Duplicada",
                    invitation_quota=1,
                )
