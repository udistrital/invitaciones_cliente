from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from apps.backoffice.forms import CeremonyForm, GraduateForm
from apps.ceremonies.models import Ceremony
from apps.graduates.models import Graduate
from apps.invitations.models import Invitation
from apps.invitations.services import (
    build_download_url,
    build_validation_url,
    cancel_invitation,
    issue_invitations_for_ceremony,
    issue_invitations_for_graduate,
    rotate_invitation_token,
)


@method_decorator(staff_member_required, name="dispatch")
class BackofficeDashboardView(TemplateView):
    template_name = "backoffice/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["metrics"] = [
            ("Ceremonias", Ceremony.objects.count()),
            ("Graduandos", Graduate.objects.count()),
            ("Invitaciones", Invitation.objects.count()),
            ("Invitaciones usadas", Invitation.objects.filter(status=Invitation.Status.USED).count()),
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
        response = super().form_valid(form)
        messages.success(self.request, "Ceremonia creada correctamente.")
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Nueva ceremonia"
        context["page_description"] = "Registra los datos base de una ceremonia de grado."
        context["cancel_url"] = reverse("backoffice:ceremony-list")
        return context


@method_decorator(staff_member_required, name="dispatch")
class CeremonyUpdateView(UpdateView):
    model = Ceremony
    form_class = CeremonyForm
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


@method_decorator(staff_member_required, name="dispatch")
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
        query = self.request.GET.get("q", "").strip()
        ceremony_id = self.request.GET.get("ceremony", "").strip()
        status = self.request.GET.get("status", "").strip()

        if query:
            queryset = queryset.filter(
                Q(code__icontains=query)
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
        context["ceremonies"] = Ceremony.objects.order_by("-scheduled_at")
        context["status_choices"] = Invitation.Status.choices

        for invitation in context["invitations"]:
            invitation.validation_url = build_validation_url(invitation, request=self.request)
            invitation.download_url = build_download_url(invitation, request=self.request)

        return context


@method_decorator(staff_member_required, name="dispatch")
class InvitationDetailView(DetailView):
    model = Invitation
    template_name = "backoffice/invitation_detail.html"
    context_object_name = "invitation"

    def get_queryset(self):
        return Invitation.objects.select_related(
            "graduate",
            "graduate__ceremony",
            "used_by",
            "used_access_point",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        invitation = self.object
        context["validation_url"] = build_validation_url(invitation, request=self.request)
        context["download_url"] = build_download_url(invitation, request=self.request)
        context["validation_logs"] = invitation.validation_logs.select_related(
            "validator",
            "access_point",
        ).order_by("-validated_at")[:20]
        return context


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
