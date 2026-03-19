from django.contrib import admin

from apps.ceremonies.models import Ceremony


@admin.register(Ceremony)
class CeremonyAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "scheduled_at", "venue", "status")
    list_filter = ("status", "scheduled_at")
    search_fields = ("code", "name", "venue")
    ordering = ("scheduled_at", "name")
