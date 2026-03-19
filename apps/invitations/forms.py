from django import forms

from apps.invitations.models import AccessPoint


class InvitationUseForm(forms.Form):
    token = forms.CharField(widget=forms.HiddenInput())
    access_point = forms.ModelChoiceField(
        queryset=AccessPoint.objects.none(),
        required=False,
        empty_label="Punto de acceso (opcional)",
        label="Punto de acceso",
    )

    def __init__(self, *args, ceremony=None, **kwargs):
        super().__init__(*args, **kwargs)
        if ceremony is not None:
            self.fields["access_point"].queryset = ceremony.access_points.filter(
                is_active=True
            ).order_by("name")
