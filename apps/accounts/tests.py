from unittest.mock import Mock, patch

from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import ExternalIdentity
from apps.accounts.services import (
    AUTHENTICATION_MID_PROFILE_SESSION_KEY,
    AuthenticationMidError,
    OIDCAccessDenied,
    OIDCAuthenticationError,
    OIDC_NEXT_SESSION_KEY,
    build_institutional_profile,
    fetch_authentication_mid_profile,
    get_oidc_settings,
    provision_user_from_claims,
)


OIDC_TEST_SETTINGS = {
    "SSO_ENABLED": True,
    "OIDC_WSO2_SERVER_METADATA_URL": "https://wso2.example.com/oauth2/oidcdiscovery/.well-known/openid-configuration",
    "OIDC_WSO2_CLIENT_ID": "client-id",
    "OIDC_WSO2_CLIENT_SECRET": "client-secret",
    "OIDC_WSO2_STAFF_ROLE": "ceremonias.staff",
    "OIDC_WSO2_ROLE_CLAIM": "roles",
    "OIDC_WSO2_EMAIL_CLAIM": "email",
    "OIDC_WSO2_USERNAME_CLAIM": "preferred_username",
    "OIDC_WSO2_NAME_CLAIM": "name",
    "OIDC_POST_LOGOUT_REDIRECT_URL": "http://testserver/gestion/",
}

AUTHENTICATION_MID_TEST_SETTINGS = {
    "AUTHENTICATION_MID_ENABLED": True,
    "AUTHENTICATION_MID_USER_ROLE_URL": "https://autenticacion.example.edu.co/token/userRol",
    "AUTHENTICATION_MID_TIMEOUT_SECONDS": 5.0,
    "AUTHENTICATION_MID_ROLE_FIELD": "role",
    "AUTHENTICATION_MID_DOCUMENT_FIELD": "documento",
    "AUTHENTICATION_MID_COMPOSED_DOCUMENT_FIELD": "documento_compuesto",
    "AUTHENTICATION_MID_EMAIL_FIELD": "email",
    "AUTHENTICATION_MID_FAMILY_NAME_FIELD": "FamilyName",
    "AUTHENTICATION_MID_STUDENT_CODE_FIELD": "Codigo",
    "AUTHENTICATION_MID_STATE_FIELD": "Estado",
}


class AccountsViewTest(TestCase):
    def test_wso2_login_view_falls_back_to_admin_when_sso_is_disabled(self):
        response = self.client.get(
            reverse("accounts:wso2-login"),
            {"next": reverse("backoffice:dashboard")},
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("admin:login"), response["Location"])

    @override_settings(**OIDC_TEST_SETTINGS)
    def test_wso2_callback_creates_staff_session_for_authorized_user(self):
        session = self.client.session
        session[OIDC_NEXT_SESSION_KEY] = reverse("backoffice:dashboard")
        session.save()

        mock_client = Mock()
        mock_client.authorize_access_token.return_value = {"id_token": "header.payload"}
        mock_client.parse_id_token.return_value = {
            "iss": "https://wso2.example.com/oauth2/token",
            "sub": "8fd2d570-f534-4b6d-b8ee-0c0ab3c06d13",
            "email": "secretaria@example.edu.co",
            "name": "Secretaria Academica",
            "preferred_username": "secretaria",
            "roles": ["ceremonias.staff"],
        }

        with patch(
            "apps.accounts.services.get_wso2_oauth_client",
            return_value=mock_client,
        ):
            response = self.client.get(reverse("accounts:wso2-callback"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("backoffice:dashboard"))
        self.assertIn("_auth_user_id", self.client.session)
        identity = ExternalIdentity.objects.get(provider=ExternalIdentity.Provider.WSO2)
        self.assertEqual(identity.user.email, "secretaria@example.edu.co")
        self.assertTrue(identity.user.is_staff)

    @override_settings(**OIDC_TEST_SETTINGS)
    def test_wso2_callback_rejects_user_without_required_role(self):
        session = self.client.session
        session[OIDC_NEXT_SESSION_KEY] = reverse("backoffice:dashboard")
        session.save()

        mock_client = Mock()
        mock_client.authorize_access_token.return_value = {"id_token": "header.payload"}
        mock_client.parse_id_token.return_value = {
            "iss": "https://wso2.example.com/oauth2/token",
            "sub": "e76b17fc-4cf2-44e8-a4df-b18a04d1ff81",
            "email": "docente@example.edu.co",
            "name": "Usuario Sin Rol",
            "roles": ["otro.rol"],
        }

        with patch(
            "apps.accounts.services.get_wso2_oauth_client",
            return_value=mock_client,
        ):
            response = self.client.get(reverse("accounts:wso2-callback"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("accounts:access-denied"))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertFalse(ExternalIdentity.objects.exists())

    @override_settings(**OIDC_TEST_SETTINGS, **AUTHENTICATION_MID_TEST_SETTINGS)
    def test_wso2_callback_uses_authentication_mid_profile_for_staff_access(self):
        session = self.client.session
        session[OIDC_NEXT_SESSION_KEY] = reverse("backoffice:dashboard")
        session.save()

        mock_client = Mock()
        mock_client.authorize_access_token.return_value = {
            "access_token": "outlook-access-token",
            "id_token": "header.payload",
        }
        mock_client.parse_id_token.return_value = {
            "iss": "https://login.microsoftonline.com/tenant/v2.0",
            "sub": "8fd2d570-f534-4b6d-b8ee-0c0ab3c06d13",
            "email": "secretaria@example.edu.co",
            "name": "Secretaria Academica",
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "role": ["ceremonias.staff"],
            "documento": "80761795",
            "documento_compuesto": "CC80761795",
            "email": "secretaria@example.edu.co",
            "FamilyName": "CASTELLANOS JIMENEZ",
            "Codigo": "20012020083",
            "Estado": "E",
        }

        with patch(
            "apps.accounts.services.get_wso2_oauth_client",
            return_value=mock_client,
        ):
            with patch(
                "apps.accounts.services.requests.post",
                return_value=mock_response,
            ) as post:
                response = self.client.get(reverse("accounts:wso2-callback"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("backoffice:dashboard"))
        post.assert_called_once()
        _, kwargs = post.call_args
        self.assertEqual(kwargs["json"], {"user": "secretaria@example.edu.co"})
        self.assertEqual(
            kwargs["headers"]["Authorization"],
            "Bearer outlook-access-token",
        )
        profile = self.client.session[AUTHENTICATION_MID_PROFILE_SESSION_KEY]
        self.assertEqual(profile["email"], "secretaria@example.edu.co")
        self.assertEqual(profile["document"], "80761795")
        self.assertEqual(profile["student_code"], "20012020083")
        self.assertIn("_auth_user_id", self.client.session)
        self.assertTrue(ExternalIdentity.objects.exists())

    @override_settings(**OIDC_TEST_SETTINGS, **AUTHENTICATION_MID_TEST_SETTINGS)
    def test_wso2_callback_does_not_create_local_user_for_student_profile(self):
        session = self.client.session
        session[OIDC_NEXT_SESSION_KEY] = reverse("backoffice:dashboard")
        session.save()

        mock_client = Mock()
        mock_client.authorize_access_token.return_value = {
            "access_token": "outlook-access-token",
            "id_token": "header.payload",
        }
        mock_client.parse_id_token.return_value = {
            "iss": "https://login.microsoftonline.com/tenant/v2.0",
            "sub": "student-subject",
            "email": "estudiante@example.edu.co",
            "name": "Estudiante Demo",
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "role": ["ESTUDIANTE"],
            "documento": "80761795",
            "email": "estudiante@example.edu.co",
            "Codigo": "20012020083",
            "Estado": "E",
        }

        with patch(
            "apps.accounts.services.get_wso2_oauth_client",
            return_value=mock_client,
        ):
            with patch(
                "apps.accounts.services.requests.post",
                return_value=mock_response,
            ):
                response = self.client.get(reverse("accounts:wso2-callback"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("accounts:access-denied"))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertFalse(ExternalIdentity.objects.exists())
        profile = self.client.session[AUTHENTICATION_MID_PROFILE_SESSION_KEY]
        self.assertEqual(profile["email"], "estudiante@example.edu.co")
        self.assertEqual(profile["roles"], ["ESTUDIANTE"])


class AccountsServiceTest(TestCase):
    @override_settings(
        SSO_ENABLED=True,
        OIDC_WSO2_SERVER_METADATA_URL="",
        OIDC_WSO2_CLIENT_ID="",
        OIDC_WSO2_CLIENT_SECRET="",
        OIDC_WSO2_STAFF_ROLE="",
    )
    def test_get_oidc_settings_requires_configuration_when_sso_is_enabled(self):
        with self.assertRaises(ImproperlyConfigured):
            get_oidc_settings()

    @override_settings(**AUTHENTICATION_MID_TEST_SETTINGS)
    def test_build_institutional_profile_normalizes_authentication_mid_payload(self):
        profile = build_institutional_profile(
            {
                "role": ["ESTUDIANTE", "ADMIN_ITAN"],
                "documento": "80761795",
                "documento_compuesto": "CC80761795",
                "email": "jcastellanosj@udistrital.edu.co",
                "FamilyName": "CASTELLANOS JIMENEZ",
                "Codigo": "20012020083",
                "Estado": "E",
            }
        )

        self.assertEqual(profile.roles, ["ESTUDIANTE", "ADMIN_ITAN"])
        self.assertEqual(profile.document, "80761795")
        self.assertEqual(profile.composed_document, "CC80761795")
        self.assertEqual(profile.email, "jcastellanosj@udistrital.edu.co")
        self.assertEqual(profile.student_code, "20012020083")
        self.assertEqual(profile.state, "E")

    @override_settings(**AUTHENTICATION_MID_TEST_SETTINGS)
    def test_fetch_authentication_mid_profile_posts_bearer_token_and_user(self):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "role": ["ESTUDIANTE"],
            "documento": "80761795",
            "email": "jcastellanosj@udistrital.edu.co",
            "Codigo": "20012020083",
            "Estado": "E",
        }

        with patch(
            "apps.accounts.services.requests.post",
            return_value=mock_response,
        ) as post:
            profile = fetch_authentication_mid_profile(
                access_token="token-outlook",
                user_email="jcastellanosj@udistrital.edu.co",
            )

        post.assert_called_once()
        _, kwargs = post.call_args
        self.assertEqual(kwargs["json"], {"user": "jcastellanosj@udistrital.edu.co"})
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer token-outlook")
        self.assertEqual(profile.roles, ["ESTUDIANTE"])

    @override_settings(**AUTHENTICATION_MID_TEST_SETTINGS)
    def test_fetch_authentication_mid_profile_rejects_error_response(self):
        mock_response = Mock()
        mock_response.status_code = 401

        with patch(
            "apps.accounts.services.requests.post",
            return_value=mock_response,
        ):
            with self.assertRaises(AuthenticationMidError):
                fetch_authentication_mid_profile(
                    access_token="token-outlook",
                    user_email="jcastellanosj@udistrital.edu.co",
                )

    @override_settings(**OIDC_TEST_SETTINGS)
    def test_provision_user_from_claims_creates_local_staff_user_and_identity(self):
        user = provision_user_from_claims(
            provider=ExternalIdentity.Provider.WSO2,
            claims={
                "iss": "https://wso2.example.com/oauth2/token",
                "sub": "5b6b1d72-a05f-4033-a3cb-ec71ea1bffbf",
                "email": "coordinacion@example.edu.co",
                "name": "Coordinacion Academica",
                "preferred_username": "coordinacion",
                "roles": ["ceremonias.staff"],
            },
        )

        identity = ExternalIdentity.objects.get(user=user)
        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.email, "coordinacion@example.edu.co")
        self.assertEqual(identity.issuer, "https://wso2.example.com/oauth2/token")
        self.assertEqual(identity.subject, "5b6b1d72-a05f-4033-a3cb-ec71ea1bffbf")

    @override_settings(**OIDC_TEST_SETTINGS)
    def test_provision_user_from_claims_requires_subject_claim(self):
        with self.assertRaises(OIDCAuthenticationError):
            provision_user_from_claims(
                provider=ExternalIdentity.Provider.WSO2,
                claims={
                    "iss": "https://wso2.example.com/oauth2/token",
                    "email": "coordinacion@example.edu.co",
                    "roles": ["ceremonias.staff"],
                },
            )

    @override_settings(**OIDC_TEST_SETTINGS)
    def test_provision_user_from_claims_requires_staff_role(self):
        with self.assertRaises(OIDCAccessDenied):
            provision_user_from_claims(
                provider=ExternalIdentity.Provider.WSO2,
                claims={
                    "iss": "https://wso2.example.com/oauth2/token",
                    "sub": "01d4ec25-324d-4b36-8adc-434dd3ed3774",
                    "email": "coordinacion@example.edu.co",
                    "roles": ["otro.rol"],
                },
            )

    @override_settings(**OIDC_TEST_SETTINGS)
    def test_provision_user_from_claims_reuses_existing_identity_and_syncs_data(self):
        user = provision_user_from_claims(
            provider=ExternalIdentity.Provider.WSO2,
            claims={
                "iss": "https://wso2.example.com/oauth2/token",
                "sub": "c9f8019e-8f72-4dd3-a503-c59e0e6db8dc",
                "email": "registro@example.edu.co",
                "name": "Registro Academico",
                "preferred_username": "registro",
                "roles": ["ceremonias.staff"],
            },
        )

        updated_user = provision_user_from_claims(
            provider=ExternalIdentity.Provider.WSO2,
            claims={
                "iss": "https://wso2.example.com/oauth2/token",
                "sub": "c9f8019e-8f72-4dd3-a503-c59e0e6db8dc",
                "email": "registro-nuevo@example.edu.co",
                "name": "Registro Academico Central",
                "preferred_username": "registro.central",
                "roles": ["ceremonias.staff"],
            },
        )

        identity = ExternalIdentity.objects.get(
            provider=ExternalIdentity.Provider.WSO2,
            subject="c9f8019e-8f72-4dd3-a503-c59e0e6db8dc",
        )
        self.assertEqual(updated_user.pk, user.pk)
        self.assertEqual(updated_user.email, "registro-nuevo@example.edu.co")
        self.assertEqual(updated_user.first_name, "Registro")
        self.assertEqual(updated_user.last_name, "Academico Central")
        self.assertIsNotNone(identity.last_login_at)
