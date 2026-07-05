from django.contrib import admin

from .models import OutboxEntry


@admin.register(OutboxEntry)
class OutboxEntryAdmin(admin.ModelAdmin):
    list_display = ["table_name", "record_id", "operation", "branch_id", "attempted", "synced_at", "created_at"]
    list_filter = ["operation", "table_name", "branch_id"]
    readonly_fields = [f.name for f in OutboxEntry._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False