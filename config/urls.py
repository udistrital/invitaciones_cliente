from django.contrib import admin
from django.urls import include, path

from apps.accounts.views import wso2_root_callback_view
from apps.core.views import health_check


urlpatterns = [
    path("", wso2_root_callback_view, name="wso2-root-callback"),
    path("admin/", admin.site.urls),
    path("auth/", include(("apps.accounts.urls", "accounts"), namespace="accounts")),
    path("health/", health_check, name="health-check"),
    path("gestion/", include(("apps.backoffice.urls", "backoffice"), namespace="backoffice")),
    path("invitaciones/", include("apps.invitations.urls")),
]
