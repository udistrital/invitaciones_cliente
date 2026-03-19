import io

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.ceremonies.models import Ceremony
from apps.graduates.models import Graduate
from apps.invitations.models import AccessPoint, Invitation, ValidationLog
from apps.invitations.services import (
    InvalidInvitationToken,
    generate_invitation_pdf,
    generate_invitation_token,
    generate_qr_code_png,
    get_invitation_from_token,
    issue_invitations_for_graduate,
    rotate_invitation_token,
)


class InvitationModelTest(TestCase):
    def setUp(self):
        self.ceremony = Ceremony.objects.create(
            code="GRADOS-2026-01",
            name="Ceremonia Central",
            scheduled_at=timezone.now(),
            venue="Auditorio Sabio Caldas",
        )
        self.graduate = Graduate.objects.create(
            ceremony=self.ceremony,
            document_number="12345678",
            full_name="Laura Perez",
            academic_program="Ingenieria de Sistemas",
            invitation_quota=2,
        )
        self.other_ceremony = Ceremony.objects.create(
            code="GRADOS-2026-02",
            name="Ceremonia Alterna",
            scheduled_at=timezone.now(),
            venue="Auditorio Ingeniería",
        )
        self.access_point = AccessPoint.objects.create(
            ceremony=self.ceremony,
            code="PUERTA-1",
            name="Puerta principal",
        )
        self.other_access_point = AccessPoint.objects.create(
            ceremony=self.other_ceremony,
            code="PUERTA-1",
            name="Puerta alterna",
        )
        self.user = get_user_model().objects.create_user(
            username="validator1",
            password="secret123",
        )

    def test_invitation_generates_public_id_code_and_default_token_version(self):
        invitation = Invitation.objects.create(
            graduate=self.graduate,
            sequence_number=1,
        )

        self.assertIsNotNone(invitation.public_id)
        self.assertTrue(invitation.code.startswith("INV-"))
        self.assertEqual(invitation.token_version, 1)
        self.assertEqual(invitation.status, Invitation.Status.CREATED)

    def test_invitation_rejects_duplicate_sequence_for_same_graduate(self):
        Invitation.objects.create(graduate=self.graduate, sequence_number=1)

        with self.assertRaises(ValidationError):
            Invitation.objects.create(graduate=self.graduate, sequence_number=1)

    def test_invitation_rejects_sequence_above_graduate_quota(self):
        with self.assertRaises(ValidationError):
            Invitation.objects.create(graduate=self.graduate, sequence_number=3)

    def test_invitation_rejects_inconsistent_status_dates(self):
        with self.assertRaises(ValidationError):
            Invitation.objects.create(
                graduate=self.graduate,
                sequence_number=1,
                status=Invitation.Status.USED,
            )

    def test_invitation_rejects_access_point_from_other_ceremony(self):
        invitation = Invitation(
            graduate=self.graduate,
            sequence_number=1,
            status=Invitation.Status.USED,
            used_at=timezone.now(),
            used_access_point=self.other_access_point,
        )

        with self.assertRaises(ValidationError):
            invitation.save()

    def test_access_point_allows_same_code_in_different_ceremonies(self):
        self.assertEqual(self.access_point.code, self.other_access_point.code)
        self.assertNotEqual(
            self.access_point.ceremony_id,
            self.other_access_point.ceremony_id,
        )

    def test_access_point_rejects_duplicate_code_in_same_ceremony(self):
        duplicated = AccessPoint(
            ceremony=self.ceremony,
            code="PUERTA-1",
            name="Puerta duplicada",
        )

        with self.assertRaises(ValidationError):
            duplicated.full_clean()

    def test_validation_log_defaults_to_not_marked_used(self):
        invitation = Invitation.objects.create(
            graduate=self.graduate,
            sequence_number=1,
        )
        log = ValidationLog.objects.create(
            invitation=invitation,
            result=ValidationLog.Result.VALID,
        )

        self.assertFalse(log.marked_as_used)

    def test_validation_log_supports_anonymous_validator_and_access_point(self):
        invitation = Invitation.objects.create(
            graduate=self.graduate,
            sequence_number=1,
        )
        log = ValidationLog.objects.create(
            invitation=invitation,
            access_point=self.access_point,
            device_label="Tablet ingreso norte",
            source_ip="10.0.0.15",
            user_agent="Mozilla/5.0",
            result=ValidationLog.Result.VALID,
        )

        self.assertIsNone(log.validator)
        self.assertEqual(log.access_point, self.access_point)
        self.assertEqual(log.device_label, "Tablet ingreso norte")

    def test_validation_log_rejects_marked_as_used_without_invitation(self):
        with self.assertRaises(ValidationError):
            ValidationLog.objects.create(
                result=ValidationLog.Result.INVALID_TOKEN,
                validator=self.user,
                access_point=self.access_point,
                marked_as_used=True,
            )

    def test_validation_log_rejects_access_point_from_other_ceremony(self):
        invitation = Invitation.objects.create(
            graduate=self.graduate,
            sequence_number=1,
        )

        with self.assertRaises(ValidationError):
            ValidationLog.objects.create(
                invitation=invitation,
                validator=self.user,
                access_point=self.other_access_point,
                result=ValidationLog.Result.VALID,
            )

    def test_issue_invitations_for_graduate_creates_up_to_quota(self):
        invitations = issue_invitations_for_graduate(self.graduate)

        self.assertEqual(len(invitations), 2)
        self.assertEqual(
            [invitation.sequence_number for invitation in invitations],
            [1, 2],
        )

    def test_generate_invitation_token_is_stable_until_regeneration(self):
        invitation = Invitation.objects.create(
            graduate=self.graduate,
            sequence_number=1,
        )

        token_1 = generate_invitation_token(invitation)
        token_2 = generate_invitation_token(invitation)

        self.assertEqual(token_1, token_2)
        self.assertEqual(get_invitation_from_token(token_1), invitation)

    def test_rotate_invitation_token_invalidates_previous_token(self):
        invitation = Invitation.objects.create(
            graduate=self.graduate,
            sequence_number=1,
        )
        old_token = generate_invitation_token(invitation)

        rotate_invitation_token(invitation)

        with self.assertRaises(InvalidInvitationToken):
            get_invitation_from_token(old_token)

    def test_generate_qr_code_png_returns_png_bytes(self):
        invitation = Invitation.objects.create(
            graduate=self.graduate,
            sequence_number=1,
        )

        png_bytes = generate_qr_code_png(invitation)

        self.assertTrue(png_bytes.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_generate_invitation_pdf_returns_pdf_bytes(self):
        invitation = Invitation.objects.create(
            graduate=self.graduate,
            sequence_number=1,
        )

        pdf_bytes = generate_invitation_pdf(invitation)

        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        self.assertIn(invitation.code.encode("utf-8"), pdf_bytes)
        self.assertIn(b"Laura Perez", pdf_bytes)

    def test_validation_endpoint_accepts_signed_token(self):
        invitation = Invitation.objects.create(
            graduate=self.graduate,
            sequence_number=1,
        )
        token = generate_invitation_token(invitation)

        response = self.client.get(
            reverse("invitation-validate"),
            {"token": token},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["invitation_code"], invitation.code)

    def test_pdf_download_endpoint_returns_pdf(self):
        invitation = Invitation.objects.create(
            graduate=self.graduate,
            sequence_number=1,
        )
        token = generate_invitation_token(invitation)

        response = self.client.get(
            reverse("invitation-download-pdf"),
            {"token": token},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_qr_preview_endpoint_returns_png(self):
        invitation = Invitation.objects.create(
            graduate=self.graduate,
            sequence_number=1,
        )

        response = self.client.get(
            reverse("invitation-qr-image", kwargs={"public_id": invitation.public_id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertTrue(response.content.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_issue_invitations_command_outputs_links(self):
        output = io.StringIO()

        call_command(
            "issue_invitations",
            graduate_id=self.graduate.pk,
            stdout=output,
        )

        command_output = output.getvalue()
        self.assertIn("invitaciones listas", command_output)
        self.assertIn("http://127.0.0.1:8000/invitaciones/validar/", command_output)

    def test_regenerate_invitation_command_increments_token_version(self):
        invitation = Invitation.objects.create(
            graduate=self.graduate,
            sequence_number=1,
        )
        output = io.StringIO()

        call_command(
            "regenerate_invitation",
            code=invitation.code,
            stdout=output,
        )

        invitation.refresh_from_db()
        self.assertEqual(invitation.token_version, 2)
