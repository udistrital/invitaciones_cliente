from django import forms
from django.utils import timezone

from apps.ceremonies.models import Ceremony
from apps.graduates.models import Graduate


class CeremonyForm(forms.ModelForm):
    scheduled_at = forms.DateTimeField(
        label="Fecha y hora",
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local"},
            format="%Y-%m-%dT%H:%M",
        ),
        input_formats=["%Y-%m-%dT%H:%M"],
    )

    class Meta:
        model = Ceremony
        fields = ("code", "name", "scheduled_at", "venue", "status")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.scheduled_at:
            self.initial["scheduled_at"] = timezone.localtime(
                self.instance.scheduled_at
            ).strftime("%Y-%m-%dT%H:%M")


class GraduateForm(forms.ModelForm):
    invitation_quota = forms.IntegerField(min_value=0, label="Cantidad de invitaciones")

    class Meta:
        model = Graduate
        fields = (
            "ceremony",
            "student_code",
            "document_number",
            "full_name",
            "academic_program",
            "email",
            "invitation_quota",
        )
