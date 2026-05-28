from typing import Optional

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.ceremonies.models import Ceremony
from apps.graduates.models import Graduate
from apps.invitations.models import Invitation
from apps.invitations.services import (
    generate_invitation_token,
    issue_invitations_for_graduate,
)


class InvitationSmokeTest(TestCase):
    def setUp(self):
        self._sequence = 0
        self.validator = get_user_model().objects.create_user(
            username="validator-smoke",
            password="secret123",
            is_staff=True,
        )
        self.client.force_login(self.validator)

    def _next_suffix(self) -> int:
        self._sequence += 1
        return self._sequence

    def _create_ceremony(self) -> Ceremony:
        suffix = self._next_suffix()
        return Ceremony.objects.create(
            code=f"GRADOS-2026-{suffix:02d}",
            name=f"Ceremonia {suffix}",
            scheduled_at=timezone.now(),
            venue=f"Auditorio {suffix}",
            status=Ceremony.Status.SCHEDULED,
        )

    def _create_graduate(self, ceremony: Optional[Ceremony] = None) -> Graduate:
        ceremony = ceremony or self._create_ceremony()
        suffix = self._next_suffix()
        return Graduate.objects.create(
            ceremony=ceremony,
            document_number=f"1000{suffix:04d}",
            full_name=f"Graduando {suffix}",
            academic_program="Ingenieria de Sistemas",
            invitation_quota=3,
        )

    def _issue_first_invitation(self, graduate: Optional[Graduate] = None) -> Invitation:
        graduate = graduate or self._create_graduate()
        invitations = issue_invitations_for_graduate(graduate)
        return invitations[0]

    def _build_token(self, invitation: Invitation) -> str:
        return generate_invitation_token(invitation)

    def _validate_json(self, token: str):
        return self.client.get(
            reverse("invitation-validate"),
            {"token": token, "format": "json"},
        )

    def test_can_create_ceremony(self):
        ceremony = self._create_ceremony()

        self.assertIsNotNone(ceremony.pk)
        self.assertEqual(ceremony.status, Ceremony.Status.SCHEDULED)
        self.assertTrue(ceremony.code.startswith("GRADOS-2026-"))

    def test_can_create_graduate(self):
        ceremony = self._create_ceremony()
        graduate = self._create_graduate(ceremony=ceremony)

        self.assertIsNotNone(graduate.pk)
        self.assertEqual(graduate.ceremony, ceremony)
        self.assertEqual(graduate.invitation_quota, 3)

    def test_can_generate_invitation(self):
        graduate = self._create_graduate()
        invitation = self._issue_first_invitation(graduate=graduate)

        self.assertIsNotNone(invitation.pk)
        self.assertEqual(invitation.graduate, graduate)
        self.assertEqual(invitation.sequence_number, 1)
        self.assertEqual(invitation.status, Invitation.Status.CREATED)

    def test_tokens_are_unique_for_different_invitations(self):
        graduate = self._create_graduate()
        invitations = issue_invitations_for_graduate(graduate)

        token_1 = self._build_token(invitations[0])
        token_2 = self._build_token(invitations[1])

        self.assertNotEqual(token_1, token_2)

    def test_valid_invitation_is_accepted(self):
        invitation = self._issue_first_invitation()
        token = self._build_token(invitation)

        response = self._validate_json(token)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], "valid")
        self.assertEqual(response.json()["invitation"]["code"], invitation.code)

    def test_used_invitation_is_rejected(self):
        invitation = Invitation.objects.create(
            graduate=self._create_graduate(),
            sequence_number=1,
            status=Invitation.Status.USED,
            used_at=timezone.now(),
        )
        token = self._build_token(invitation)

        response = self._validate_json(token)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], "used")
        self.assertIn("ya fue utilizada", response.json()["message"])

    def test_cancelled_invitation_is_rejected(self):
        invitation = Invitation.objects.create(
            graduate=self._create_graduate(),
            sequence_number=1,
            status=Invitation.Status.CANCELLED,
            cancelled_at=timezone.now(),
        )
        token = self._build_token(invitation)

        response = self._validate_json(token)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], "cancelled")
        self.assertIn("anulada", response.json()["message"])

    def test_invalid_or_missing_invitation_is_rejected(self):
        response = self._validate_json("token-invalido")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], "not_found")
        self.assertIn("no es valido", response.json()["message"])
