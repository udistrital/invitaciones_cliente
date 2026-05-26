import io

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from openpyxl import Workbook

from apps.ceremonies.models import Ceremony
from apps.graduates.models import Graduate, GraduateImportBatch
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
            document_type="CC",
            document_number="12345678",
            full_name="Laura Perez",
            academic_program="Ingenieria de Sistemas",
            invitation_quota=2,
        )

    def build_excel_upload(self, rows, name="graduandos.xlsx"):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "graduandos"
        worksheet.append(
            [
                "codigo_estudiantil",
                "tipo_documento",
                "numero_documento",
                "nombre_completo",
                "correo_institucional",
                "programa_academico",
            ]
        )
        for row in rows:
            worksheet.append(list(row))

        buffer = io.BytesIO()
        workbook.save(buffer)
        return SimpleUploadedFile(
            name,
            buffer.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )

    def test_dashboard_requires_staff_authentication(self):
        response = self.client.get(reverse("backoffice:dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:wso2-login"), response["Location"])

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

    def test_staff_can_create_ceremony_with_excel_and_preview_without_importing(self):
        self.client.force_login(self.staff_user)
        upload = self.build_excel_upload(
            rows=[
                (
                    "20261001",
                    "CC",
                    "10000001",
                    "Laura Perez",
                    "laura@example.com",
                    "Ingenieria de Sistemas",
                )
            ]
        )

        response = self.client.post(
            reverse("backoffice:ceremony-create"),
            {
                "code": "GRADOS-2026-03",
                "name": "Ceremonia Sur",
                "scheduled_at": "2026-04-21T18:00",
                "venue": "Auditorio Sur",
                "status": Ceremony.Status.SCHEDULED,
                "graduates_file": upload,
            },
        )

        ceremony = Ceremony.objects.get(code="GRADOS-2026-03")
        batch = GraduateImportBatch.objects.get(ceremony=ceremony)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(batch.status, GraduateImportBatch.Status.VALIDATED)
        self.assertEqual(ceremony.graduates.count(), 0)
        self.assertIn(
            reverse(
                "backoffice:ceremony-graduate-import-preview",
                kwargs={"pk": ceremony.pk, "batch_id": batch.pk},
            ),
            response["Location"],
        )

    def test_staff_can_upload_excel_for_existing_ceremony(self):
        self.client.force_login(self.staff_user)
        upload = self.build_excel_upload(
            rows=[
                (
                    "20261002",
                    "CC",
                    "10000002",
                    "Carlos Ruiz",
                    "carlos@example.com",
                    "Ingenieria Industrial",
                )
            ]
        )

        response = self.client.post(
            reverse(
                "backoffice:ceremony-graduate-import-upload",
                kwargs={"pk": self.ceremony.pk},
            ),
            {"graduates_file": upload},
        )

        batch = GraduateImportBatch.objects.get(ceremony=self.ceremony)
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse(
                "backoffice:ceremony-graduate-import-preview",
                kwargs={"pk": self.ceremony.pk, "batch_id": batch.pk},
            ),
            response["Location"],
        )

    def test_staff_can_confirm_valid_import_batch(self):
        self.client.force_login(self.staff_user)
        upload = self.build_excel_upload(
            rows=[
                (
                    "20261002",
                    "CC",
                    "10000002",
                    "Carlos Ruiz",
                    "carlos@example.com",
                    "Ingenieria Industrial",
                )
            ]
        )
        preview_response = self.client.post(
            reverse(
                "backoffice:ceremony-graduate-import-upload",
                kwargs={"pk": self.ceremony.pk},
            ),
            {"graduates_file": upload},
        )
        batch = GraduateImportBatch.objects.get(ceremony=self.ceremony)

        response = self.client.post(
            reverse(
                "backoffice:ceremony-graduate-import-confirm",
                kwargs={"pk": self.ceremony.pk, "batch_id": batch.pk},
            ),
            follow=True,
        )

        batch.refresh_from_db()
        self.assertEqual(preview_response.status_code, 302)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(batch.status, GraduateImportBatch.Status.CONFIRMED)
        self.assertTrue(
            Graduate.objects.filter(
                ceremony=self.ceremony,
                document_number="10000002",
            ).exists()
        )
        imported_graduate = Graduate.objects.get(
            ceremony=self.ceremony,
            document_number="10000002",
        )
        self.assertEqual(imported_graduate.invitations.count(), 3)
        self.assertContains(response, "Importacion confirmada correctamente")

    def test_staff_can_download_graduate_template(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(
            reverse("backoffice:ceremony-graduate-template-download")
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn("plantilla-graduandos.xlsx", response["Content-Disposition"])

    def test_staff_can_create_graduate(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("backoffice:graduate-create"),
            {
                "ceremony": self.ceremony.pk,
                "student_code": "20201002",
                "document_type": "CC",
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

    def test_staff_can_regenerate_unused_invitation(self):
        self.client.force_login(self.staff_user)
        invitation = Invitation.objects.create(
            graduate=self.graduate,
            sequence_number=1,
        )

        response = self.client.post(
            reverse("backoffice:invitation-regenerate", kwargs={"pk": invitation.pk}),
            follow=True,
        )

        invitation.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(invitation.token_version, 2)
        self.assertContains(response, "fue regenerada")
        self.assertContains(response, "Nueva version")

    def test_staff_cannot_regenerate_used_invitation(self):
        self.client.force_login(self.staff_user)
        invitation = Invitation.objects.create(
            graduate=self.graduate,
            sequence_number=1,
            status=Invitation.Status.USED,
            used_at=timezone.now(),
            used_by=self.staff_user,
        )

        response = self.client.post(
            reverse("backoffice:invitation-regenerate", kwargs={"pk": invitation.pk}),
            follow=True,
        )

        invitation.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(invitation.token_version, 1)
        self.assertContains(response, "ya fue utilizada")

    def test_staff_cannot_regenerate_cancelled_invitation(self):
        self.client.force_login(self.staff_user)
        invitation = Invitation.objects.create(
            graduate=self.graduate,
            sequence_number=1,
            status=Invitation.Status.CANCELLED,
            cancelled_at=timezone.now(),
        )

        response = self.client.post(
            reverse("backoffice:invitation-regenerate", kwargs={"pk": invitation.pk}),
            follow=True,
        )

        invitation.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(invitation.token_version, 1)
        self.assertContains(response, "anulada")

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
