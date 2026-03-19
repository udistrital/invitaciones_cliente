from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.ceremonies.models import Ceremony
from apps.graduates.models import Graduate
from apps.invitations.models import Invitation, ValidationLog


class BackofficeViewTest(TestCase):
    def setUp(self):
        self.staff_user = get_user_model().objects.create_user(
            username="secretaria",
            password="secret123",
            is_staff=True,
        )
        self.ceremony = Ceremony.objects.create(
            code="GRADOS-2026-01",
            name="Ceremonia Central",
            scheduled_at=timezone.now(),
            venue="Auditorio Sabio Caldas",
        )
        self.graduate = Graduate.objects.create(
            ceremony=self.ceremony,
            student_code="20201001",
            document_number="12345678",
            full_name="Laura Perez",
            academic_program="Ingenieria de Sistemas",
            invitation_quota=2,
        )

    def test_dashboard_requires_staff_authentication(self):
        response = self.client.get(reverse("backoffice:dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("admin:login"), response["Location"])

    def test_staff_can_create_ceremony(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("backoffice:ceremony-create"),
            {
                "code": "GRADOS-2026-02",
                "name": "Ceremonia Norte",
                "scheduled_at": "2026-04-20T18:00",
                "venue": "Auditorio Norte",
                "status": Ceremony.Status.SCHEDULED,
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Ceremony.objects.filter(code="GRADOS-2026-02").exists())
        self.assertContains(response, "Ceremonia creada correctamente.")

    def test_staff_can_create_graduate(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("backoffice:graduate-create"),
            {
                "ceremony": self.ceremony.pk,
                "student_code": "20201002",
                "document_number": "87654321",
                "full_name": "Carlos Ruiz",
                "academic_program": "Ingenieria Industrial",
                "email": "carlos@example.com",
                "invitation_quota": 3,
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Graduate.objects.filter(document_number="87654321").exists())
        self.assertContains(response, "Graduando registrado correctamente.")

    def test_staff_can_generate_invitations_from_graduate_list(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse(
                "backoffice:graduate-issue-invitations",
                kwargs={"pk": self.graduate.pk},
            ),
            {"next": reverse("backoffice:graduate-list")},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Invitation.objects.filter(graduate=self.graduate).count(), 2)
        self.assertContains(response, "Se dejaron listas 2 invitaciones")

    def test_staff_can_cancel_unused_invitation(self):
        self.client.force_login(self.staff_user)
        invitation = Invitation.objects.create(
            graduate=self.graduate,
            sequence_number=1,
        )

        response = self.client.post(
            reverse("backoffice:invitation-cancel", kwargs={"pk": invitation.pk}),
            {"next": reverse("backoffice:invitation-list")},
            follow=True,
        )

        invitation.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(invitation.status, Invitation.Status.CANCELLED)
        self.assertContains(response, "fue anulada")

    def test_staff_cannot_cancel_used_invitation(self):
        self.client.force_login(self.staff_user)
        invitation = Invitation.objects.create(
            graduate=self.graduate,
            sequence_number=1,
            status=Invitation.Status.USED,
            used_at=timezone.now(),
            used_by=self.staff_user,
        )

        response = self.client.post(
            reverse("backoffice:invitation-cancel", kwargs={"pk": invitation.pk}),
            {"next": reverse("backoffice:invitation-list")},
            follow=True,
        )

        invitation.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(invitation.status, Invitation.Status.USED)
        self.assertContains(response, "ya fue utilizada")

    def test_invitation_detail_shows_validation_status(self):
        self.client.force_login(self.staff_user)
        invitation = Invitation.objects.create(
            graduate=self.graduate,
            sequence_number=1,
        )
        ValidationLog.objects.create(
            invitation=invitation,
            result=ValidationLog.Result.VALID,
        )

        response = self.client.get(
            reverse("backoffice:invitation-detail", kwargs={"pk": invitation.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, invitation.code)
        self.assertContains(response, "Historial de validacion")
