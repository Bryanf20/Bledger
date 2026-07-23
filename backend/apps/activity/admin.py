from django.contrib import admin

from .models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "is_major", "actor", "summary")
    list_filter = ("action", "is_major")
    search_fields = ("summary", "target_id")
    readonly_fields = [f.name for f in ActivityLog._meta.fields]
