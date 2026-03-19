from django.contrib import admin

from apps.graduates.models import Graduate


@admin.register(Graduate)
class GraduateAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "academic_program",
        "document_number",
        "student_code",
        "ceremony",
        "invitation_quota",
    )
    list_filter = ("ceremony",)
    search_fields = (
        "full_name",
        "academic_program",
        "document_number",
        "student_code",
        "email",
    )
    ordering = ("full_name",)
