from django.urls import path

from apps.backoffice import views


urlpatterns = [
    path("", views.BackofficeDashboardView.as_view(), name="dashboard"),
    path("ceremonias/", views.CeremonyListView.as_view(), name="ceremony-list"),
    path("ceremonias/nueva/", views.CeremonyCreateView.as_view(), name="ceremony-create"),
    path(
        "ceremonias/<int:pk>/editar/",
        views.CeremonyUpdateView.as_view(),
        name="ceremony-update",
    ),
    path(
        "ceremonias/<int:pk>/generar-invitaciones/",
        views.issue_ceremony_invitations_view,
        name="ceremony-issue-invitations",
    ),
    path("graduandos/", views.GraduateListView.as_view(), name="graduate-list"),
    path("graduandos/nuevo/", views.GraduateCreateView.as_view(), name="graduate-create"),
    path(
        "graduandos/<int:pk>/editar/",
        views.GraduateUpdateView.as_view(),
        name="graduate-update",
    ),
    path(
        "graduandos/<int:pk>/generar-invitaciones/",
        views.issue_graduate_invitations_view,
        name="graduate-issue-invitations",
    ),
    path("invitaciones/", views.InvitationListView.as_view(), name="invitation-list"),
    path(
        "invitaciones/<int:pk>/",
        views.InvitationDetailView.as_view(),
        name="invitation-detail",
    ),
    path(
        "invitaciones/<int:pk>/anular/",
        views.cancel_invitation_view,
        name="invitation-cancel",
    ),
]
