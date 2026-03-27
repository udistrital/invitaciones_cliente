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
    graduates_file = forms.FileField(
        label="Archivo de graduandos (.xlsx)",
        required=False,
        help_text=(
            "Opcional. Si lo adjuntas ahora, el sistema validara el archivo y te "
            "llevara al preview antes de importar."
        ),
        widget=forms.ClearableFileInput(attrs={"accept": ".xlsx"}),
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


class CeremonyUpdateForm(forms.ModelForm):
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
    invitation_quota = forms.IntegerField(
        min_value=0,
        initial=3,
        label="Cantidad de invitaciones",
    )

    class Meta:
        model = Graduate
        fields = (
            "ceremony",
            "student_code",
            "document_type",
            "document_number",
            "full_name",
            "academic_program",
            "email",
            "invitation_quota",
        )


class GraduateImportUploadForm(forms.Form):
    graduates_file = forms.FileField(
        label="Archivo de graduandos (.xlsx)",
        help_text="Solo se aceptan archivos Excel con extension .xlsx.",
        widget=forms.ClearableFileInput(attrs={"accept": ".xlsx"}),
    )
