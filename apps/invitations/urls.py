from django.urls import path

from apps.invitations.views import (
    invitation_pdf_download_view,
    invitation_qr_view,
    invitation_validate_view,
)


urlpatterns = [
    path("validar/", invitation_validate_view, name="invitation-validate"),
    path("descargar/", invitation_pdf_download_view, name="invitation-download-pdf"),
    path("qr/<uuid:public_id>/", invitation_qr_view, name="invitation-qr-image"),
]
