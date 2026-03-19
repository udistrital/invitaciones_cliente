from django.test import TestCase
from django.utils import timezone

from apps.ceremonies.models import Ceremony


class CeremonyModelTest(TestCase):
    def test_string_representation_uses_code_and_name(self):
        ceremony = Ceremony.objects.create(
            code="GRADOS-2026-01",
            name="Ceremonia Central",
            scheduled_at=timezone.now(),
            venue="Auditorio Sabio Caldas",
        )

        self.assertEqual(str(ceremony), "GRADOS-2026-01 - Ceremonia Central")
