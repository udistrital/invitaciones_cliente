from django.test import TestCase
from django.utils import timezone

from apps.ceremonies.models import Ceremony
from apps.graduates.models import Graduate
from apps.invitations.models import Invitation, ValidationLog


class InvitationModelTest(TestCase):
    def setUp(self):
        ceremony = Ceremony.objects.create(
            code="GRADOS-2026-01",
            name="Ceremonia Central",
            scheduled_at=timezone.now(),
            venue="Auditorio Sabio Caldas",
        )
        self.graduate = Graduate.objects.create(
            ceremony=ceremony,
            document_number="12345678",
            full_name="Laura Perez",
            invitation_quota=2,
        )

    def test_invitation_generates_public_id_and_default_status(self):
        invitation = Invitation.objects.create(graduate=self.graduate)

        self.assertIsNotNone(invitation.public_id)
        self.assertEqual(invitation.status, Invitation.Status.CREATED)

    def test_validation_log_defaults_to_not_marked_used(self):
        invitation = Invitation.objects.create(graduate=self.graduate)
        log = ValidationLog.objects.create(
            invitation=invitation,
            result=ValidationLog.Result.VALID,
        )

        self.assertFalse(log.marked_as_used)
