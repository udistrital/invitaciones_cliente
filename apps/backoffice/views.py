from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import CreateView, DetailView, FormView, ListView, TemplateView, UpdateView

from apps.accounts.decorators import (
    backoffice_staff_required as staff_member_required,
    invitation_viewer_required,
)
from apps.accounts.services import (
    get_composed_document_from_session,
    get_document_from_session,
    get_student_code_from_session,
    is_backoffice_operator,
    is_student_limited,
)
from apps.backoffice.forms import (
    CeremonyForm,
    CeremonyUpdateForm,
    GraduateForm,
    GraduateImportUploadForm,
)
from apps.ceremonies.models import Ceremony
from apps.graduates.imports import (
    build_graduate_template_workbook,
    confirm_graduate_import_batch,
    create_graduate_import_batch,
)
from apps.graduates.models import Graduate, GraduateImportBatch
from apps.invitations.models import Invitation
from apps.invitations.services import (
    build_download_url,
    build_validation_url,
    cancel_invitation,
    issue_invitations_for_ceremony,
    issue_invitations_for_graduate,
    rotate_invitation_token,
)


def build_import_summary(batch):
    return (
        f"Filas leidas: {batch.rows_total}. "
        f"Validas: {batch.rows_valid}. "
        f"Con error: {batch.rows_error}. "
        f"Graduandos creados: {batch.graduates_created}. "
        f"Graduandos actualizados: {batch.graduates_updated}. "
        f"Invitaciones creadas: {batch.invitations_created}."
    )


def normalize_identifier(value: str) -> str:
    return "".join(character for character in str(value or "") if character.isalnum()).upper()


def get_student_invitation_owner_filter(request, graduate_prefix="graduate__") -> Q:
    student_code = get_student_code_from_session(request)
    document = get_document_from_session(request)
    composed_document = get_composed_document_from_session(request)
    query = Q()

    if student_code:
        query |= Q(**{f"{graduate_prefix}student_code": student_code})
    if document:
        query |= Q(**{f"{graduate_prefix}document_number": document})
    if composed_document:
        normalized_composed = normalize_identifier(composed_document)
        if document and normalize_identifier(document) in normalized_composed:
            query |= Q(**{f"{graduate_prefix}document_number": document})

    return query


@method_decorator(staff_member_required, name="dispatch")
class BackofficeDashboardView(TemplateView):
    template_name = "backoffice/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["metrics"] = [
            ("Ceremonias", Ceremony.objects.count()),
            ("Graduandos", Graduate.objects.count()),
            ("Invitaciones", Invitation.objects.count()),
            (
                "Invitaciones usadas",
                Invitation.objects.filter(status=Invitation.Status.USED).count(),
            ),
        ]
        context["recent_ceremonies"] = Ceremony.objects.order_by("-scheduled_at")[:5]
        context["recent_invitations"] = Invitation.objects.select_related(
            "graduate",
            "graduate__ceremony",
        ).order_by("-created_at")[:5]
        return context


@method_decorator(staff_member_required, name="dispatch")
class CeremonyListView(ListView):
    model = Ceremony
    template_name = "backoffice/ceremony_list.html"
    context_object_name = "ceremonies"

    def get_queryset(self):
        queryset = Ceremony.objects.annotate(
            graduates_total=Count("graduates", distinct=True),
            invitations_total=Count("graduates__invitations", distinct=True),
            import_batches_total=Count("graduate_import_batches", distinct=True),
        ).order_by("-scheduled_at")
        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(code__icontains=query)
                | Q(name__icontains=query)
                | Q(venue__icontains=query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Ceremonias"
        context["query"] = self.request.GET.get("q", "").strip()
        return context


@method_decorator(staff_member_required, name="dispatch")
class CeremonyCreateView(CreateView):
    model = Ceremony
    form_class = CeremonyForm
    template_name = "backoffice/form.html"
    success_url = reverse_lazy("backoffice:ceremony-list")

    def form_valid(self, form):
        graduates_file = form.cleaned_data.get("graduates_file")
        self.object = form.save()

        if not graduates_file:
            messages.success(self.request, "Ceremonia creada correctamente.")
            return HttpResponseRedirect(self.get_success_url())

        batch = create_graduate_import_batch(
            ceremony=self.object,
            uploaded_file=graduates_file,
            uploaded_by=self.request.user,
        )

        if batch.preview_payload.get("can_confirm"):
            messages.success(
                self.request,
                "Ceremonia creada y archivo validado. Revisa el preview antes de confirmar.",
            )
        else:
            messages.warning(
                self.request,
                "Ceremonia creada, pero el archivo tiene observaciones y no se puede confirmar aun.",
            )

        return HttpResponseRedirect(
            reverse(
                "backoffice:ceremony-graduate-import-preview",
                kwargs={"pk": self.object.pk, "batch_id": batch.pk},
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Nueva ceremonia"
        context["page_description"] = (
            "Registra los datos base de una ceremonia y, si quieres, adjunta de una vez "
            "el Excel de graduandos para validarlo."
        )
        context["cancel_url"] = reverse("backoffice:ceremony-list")
        return context


@method_decorator(staff_member_required, name="dispatch")
class CeremonyUpdateView(UpdateView):
    model = Ceremony
    form_class = CeremonyUpdateForm
    template_name = "backoffice/form.html"
    success_url = reverse_lazy("backoffice:ceremony-list")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Ceremonia actualizada correctamente.")
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Editar ceremonia"
        context["page_description"] = "Actualiza fecha, lugar y estado de la ceremonia."
        context["cancel_url"] = reverse("backoffice:ceremony-list")
        return context


@method_decorator(staff_member_required, name="dispatch")
class CeremonyGraduateImportUploadView(FormView):
    template_name = "backoffice/graduate_import_upload.html"
    form_class = GraduateImportUploadForm

    def dispatch(self, request, *args, **kwargs):
        self.ceremony = get_object_or_404(Ceremony, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        batch = create_graduate_import_batch(
            ceremony=self.ceremony,
            uploaded_file=form.cleaned_data["graduates_file"],
            uploaded_by=self.request.user,
        )

        if batch.preview_payload.get("can_confirm"):
            messages.success(
                self.request,
                "Archivo validado. Revisa el preview y confirma la importacion.",
            )
        else:
            messages.warning(
                self.request,
                "El archivo fue validado con observaciones. Corrigelo antes de confirmar.",
            )

        return HttpResponseRedirect(
            reverse(
                "backoffice:ceremony-graduate-import-preview",
                kwargs={"pk": self.ceremony.pk, "batch_id": batch.pk},
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Cargar graduandos"
        context["page_description"] = (
            "Sube un archivo Excel para validar graduandos sobre una ceremonia ya creada."
        )
        context["ceremony"] = self.ceremony
        context["cancel_url"] = reverse("backoffice:ceremony-list")
        context["template_url"] = reverse(
            "backoffice:ceremony-graduate-template-download"
        )
        return context


@method_decorator(staff_member_required, name="dispatch")
class GraduateImportPreviewView(TemplateView):
    template_name = "backoffice/graduate_import_preview.html"

    def dispatch(self, request, *args, **kwargs):
        self.ceremony = get_object_or_404(Ceremony, pk=kwargs["pk"])
        self.batch = get_object_or_404(
            GraduateImportBatch.objects.select_related(
                "ceremony",
                "uploaded_by",
                "confirmed_by",
            ),
            pk=kwargs["batch_id"],
            ceremony=self.ceremony,
        )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        preview = self.batch.preview_payload or {}
        context["page_title"] = "Preview de importacion"
        context["page_description"] = (
            "Revisa las filas detectadas, valida las observaciones y confirma solo si el lote esta limpio."
        )
        context["ceremony"] = self.ceremony
        context["batch"] = self.batch
        context["preview"] = preview
        context["rows"] = preview.get("rows", [])
        context["file_errors"] = preview.get("file_errors", [])
        context["can_confirm"] = (
            self.batch.status == GraduateImportBatch.Status.VALIDATED
            and preview.get("can_confirm", False)
        )
        context["cancel_url"] = reverse("backoffice:ceremony-list")
        context["upload_url"] = reverse(
            "backoffice:ceremony-graduate-import-upload",
            kwargs={"pk": self.ceremony.pk},
        )
        context["graduates_url"] = (
            f"{reverse('backoffice:graduate-list')}?{urlencode({'ceremony': self.ceremony.pk})}"
        )
        return context


@method_decorator(staff_member_required, name="dispatch")
class GraduateListView(ListView):
    model = Graduate
    template_name = "backoffice/graduate_list.html"
    context_object_name = "graduates"

    def get_queryset(self):
        queryset = (
            Graduate.objects.select_related("ceremony")
            .annotate(generated_invitations=Count("invitations", distinct=True))
            .order_by("full_name")
        )
        query = self.request.GET.get("q", "").strip()
        ceremony_id = self.request.GET.get("ceremony", "").strip()

        if query:
            queryset = queryset.filter(
                Q(full_name__icontains=query)
                | Q(document_number__icontains=query)
                | Q(academic_program__icontains=query)
            )
        if ceremony_id:
            queryset = queryset.filter(ceremony_id=ceremony_id)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Graduandos"
        context["query"] = self.request.GET.get("q", "").strip()
        context["selected_ceremony"] = self.request.GET.get("ceremony", "").strip()
        context["ceremonies"] = Ceremony.objects.order_by("-scheduled_at")
        return context


@method_decorator(staff_member_required, name="dispatch")
class GraduateCreateView(CreateView):
    model = Graduate
    form_class = GraduateForm
    template_name = "backoffice/form.html"

    def get_initial(self):
        initial = super().get_initial()
        ceremony_id = self.request.GET.get("ceremony")
        if ceremony_id:
            initial["ceremony"] = ceremony_id
        initial.setdefault("invitation_quota", 3)
        return initial

    def get_success_url(self):
        return f"{reverse('backoffice:graduate-list')}?{urlencode({'ceremony': self.object.ceremony_id})}"

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Graduando registrado correctamente.")
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Nuevo graduando"
        context["page_description"] = "Registra graduandos y define el cupo de invitaciones."
        context["cancel_url"] = reverse("backoffice:graduate-list")
        return context


@method_decorator(staff_member_required, name="dispatch")
class GraduateUpdateView(UpdateView):
    model = Graduate
    form_class = GraduateForm
    template_name = "backoffice/form.html"

    def get_success_url(self):
        return f"{reverse('backoffice:graduate-list')}?{urlencode({'ceremony': self.object.ceremony_id})}"

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Graduando actualizado correctamente.")
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Editar graduando"
        context["page_description"] = "Actualiza datos personales, programa y cupo de invitaciones."
        context["cancel_url"] = reverse("backoffice:graduate-list")
        return context


@method_decorator(invitation_viewer_required, name="dispatch")
class InvitationListView(ListView):
    model = Invitation
    template_name = "backoffice/invitation_list.html"
    context_object_name = "invitations"

    def get_queryset(self):
        queryset = (
            Invitation.objects.select_related(
                "graduate",
                "graduate__ceremony",
                "used_by",
                "used_access_point",
            )
            .order_by("-created_at")
        )
        if is_student_limited(self.request):
            owner_filter = get_student_invitation_owner_filter(self.request)
            if not owner_filter:
                return queryset.none()
            queryset = queryset.filter(owner_filter)

        query = self.request.GET.get("q", "").strip()
        ceremony_id = self.request.GET.get("ceremony", "").strip()
        status = self.request.GET.get("status", "").strip()

        if query:
            code_filter = (
                Q(graduate__student_code__icontains=query)
                if is_student_limited(self.request)
                else Q(code__icontains=query)
            )
            queryset = queryset.filter(
                code_filter
                | Q(graduate__full_name__icontains=query)
                | Q(graduate__document_number__icontains=query)
            )
        if ceremony_id:
            queryset = queryset.filter(graduate__ceremony_id=ceremony_id)
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Invitaciones"
        context["query"] = self.request.GET.get("q", "").strip()
        context["selected_ceremony"] = self.request.GET.get("ceremony", "").strip()
        context["selected_status"] = self.request.GET.get("status", "").strip()
        context["can_manage_backoffice"] = is_backoffice_operator(self.request)
        context["is_student_invitation_view"] = is_student_limited(self.request)
        if context["is_student_invitation_view"]:
            owner_filter = get_student_invitation_owner_filter(
                self.request,
                graduate_prefix="graduates__",
            )
            context["ceremonies"] = (
                Ceremony.objects.filter(graduates__invitations__isnull=False)
                .filter(owner_filter)
                .distinct()
                .order_by("-scheduled_at")
                if owner_filter
                else Ceremony.objects.none()
            )
        else:
            context["ceremonies"] = Ceremony.objects.order_by("-scheduled_at")
        context["status_choices"] = Invitation.Status.choices

        for invitation in context["invitations"]:
            invitation.validation_url = (
                build_validation_url(invitation, request=self.request)
                if context["can_manage_backoffice"]
                else ""
            )
            invitation.download_url = build_download_url(
                invitation,
                request=self.request,
            )

        return context


@method_decorator(invitation_viewer_required, name="dispatch")
class InvitationDetailView(DetailView):
    model = Invitation
    template_name = "backoffice/invitation_detail.html"
    context_object_name = "invitation"

    def get_queryset(self):
        queryset = Invitation.objects.select_related(
            "graduate",
            "graduate__ceremony",
            "used_by",
            "used_access_point",
        )
        if is_student_limited(self.request):
            owner_filter = get_student_invitation_owner_filter(self.request)
            if not owner_filter:
                return queryset.none()
            queryset = queryset.filter(owner_filter)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        invitation = self.object
        context["can_manage_backoffice"] = is_backoffice_operator(self.request)
        context["is_student_invitation_view"] = is_student_limited(self.request)
        context["validation_url"] = (
            build_validation_url(invitation, request=self.request)
            if context["can_manage_backoffice"]
            else ""
        )
        context["download_url"] = build_download_url(
            invitation,
            request=self.request,
        )
        context["validation_logs"] = (
            invitation.validation_logs.select_related(
                "validator",
                "access_point",
            ).order_by("-validated_at")[:20]
            if context["can_manage_backoffice"]
            else []
        )
        return context


@staff_member_required
@require_GET
def graduate_template_download_view(request):
    workbook_bytes = build_graduate_template_workbook()
    response = HttpResponse(
        workbook_bytes,
        content_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
    )
    response["Content-Disposition"] = (
        'attachment; filename="plantilla-graduandos.xlsx"'
    )
    return response


@staff_member_required
@require_POST
def confirm_graduate_import_view(request, pk, batch_id):
    ceremony = get_object_or_404(Ceremony, pk=pk)
    batch = get_object_or_404(
        GraduateImportBatch.objects.select_related("ceremony"),
        pk=batch_id,
        ceremony=ceremony,
    )

    try:
        if batch.status != GraduateImportBatch.Status.VALIDATED:
            raise ValidationError("Este lote ya no esta disponible para confirmar.")
        confirm_graduate_import_batch(batch=batch, confirmed_by=request.user)
        messages.success(
            request,
            "Importacion confirmada correctamente. " + build_import_summary(batch),
        )
    except ValidationError as exc:
        messages.error(request, getattr(exc, "message", str(exc)))
    except Exception:
        messages.error(
            request,
            "Ocurrio un error inesperado al confirmar la importacion.",
        )

    return HttpResponseRedirect(
        reverse(
            "backoffice:ceremony-graduate-import-preview",
            kwargs={"pk": ceremony.pk, "batch_id": batch.pk},
        )
    )


@staff_member_required
@require_POST
def issue_graduate_invitations_view(request, pk):
    graduate = get_object_or_404(Graduate.objects.select_related("ceremony"), pk=pk)
    invitations = issue_invitations_for_graduate(graduate)
    messages.success(
        request,
        f"Se dejaron listas {len(invitations)} invitaciones para {graduate.full_name}.",
    )
    next_url = request.POST.get("next") or reverse("backoffice:graduate-list")
    return HttpResponseRedirect(next_url)


@staff_member_required
@require_POST
def issue_ceremony_invitations_view(request, pk):
    ceremony = get_object_or_404(Ceremony, pk=pk)
    total = issue_invitations_for_ceremony(ceremony)
    messages.success(
        request,
        f"Se prepararon {total} invitaciones para la ceremonia {ceremony.name}.",
    )
    next_url = request.POST.get("next") or reverse("backoffice:ceremony-list")
    return HttpResponseRedirect(next_url)


@staff_member_required
@require_POST
def cancel_invitation_view(request, pk):
    invitation = get_object_or_404(
        Invitation.objects.select_related("graduate", "graduate__ceremony"),
        pk=pk,
    )
    try:
        cancel_invitation(invitation)
        messages.success(request, f"La invitacion {invitation.code} fue anulada.")
    except ValidationError as exc:
        messages.error(request, str(exc))

    next_url = request.POST.get("next") or reverse(
        "backoffice:invitation-detail",
        kwargs={"pk": invitation.pk},
    )
    return HttpResponseRedirect(next_url)


@staff_member_required
@require_POST
def regenerate_invitation_view(request, pk):
    invitation = get_object_or_404(
        Invitation.objects.select_related("graduate", "graduate__ceremony"),
        pk=pk,
    )
    try:
        rotate_invitation_token(invitation)
        messages.success(
            request,
            (
                f"La invitacion {invitation.code} fue regenerada. "
                f"Nueva version: {invitation.token_version}."
            ),
        )
    except ValidationError as exc:
        messages.error(request, getattr(exc, "message", str(exc)))

    next_url = request.POST.get("next") or reverse(
        "backoffice:invitation-detail",
        kwargs={"pk": invitation.pk},
    )
    return HttpResponseRedirect(next_url)
