from django.contrib import admin

from apps.graduates.models import Graduate, GraduateImportBatch


@admin.register(Graduate)
class GraduateAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "academic_program",
        "document_type",
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


@admin.register(GraduateImportBatch)
class GraduateImportBatchAdmin(admin.ModelAdmin):
    list_display = (
        "source_filename",
        "ceremony",
        "status",
        "rows_total",
        "rows_error",
        "graduates_created",
        "graduates_updated",
        "invitations_created",
        "created_at",
    )
    list_filter = ("status", "ceremony")
    search_fields = (
        "source_filename",
        "ceremony__code",
        "ceremony__name",
        "file_sha256",
    )
    ordering = ("-created_at",)
