from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import BledgerUser, Branch


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("business_name", "branch_name", "deployment_mode", "setup_complete")
    search_fields = ("business_name", "branch_name")


@admin.register(BledgerUser)
class BledgerUserAdmin(UserAdmin):
    model = BledgerUser
    list_display = ("username", "name", "role", "branch", "is_active")
    list_filter = ("role", "is_active", "branch")
    search_fields = ("username", "name")
    ordering = ("name",)
    readonly_fields = ("pin_hash", "created_at", "updated_at")

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Profile", {"fields": ("name", "branch", "role", "pin_hash")}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Timestamps", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "name", "branch", "role", "password1", "password2"),
            },
        ),
    )