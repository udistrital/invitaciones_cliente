from django.urls import path

from apps.accounts import views


app_name = "accounts"


urlpatterns = [
    path("login/wso2/", views.wso2_login_view, name="wso2-login"),
    path("callback/wso2/", views.wso2_callback_view, name="wso2-callback"),
    path("logout/", views.logout_view, name="logout"),
    path("access-denied/", views.access_denied_view, name="access-denied"),
]
