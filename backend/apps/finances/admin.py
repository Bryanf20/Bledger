from django.contrib import admin

from .models import CashbookEntry, ExpenseCategory


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "branch_id")
    search_fields = ("name",)


@admin.register(CashbookEntry)
class CashbookEntryAdmin(admin.ModelAdmin):
    list_display = ("direction", "amount", "category", "occurred_on", "recorded_by", "branch_id")
    list_filter = ("direction",)
    search_fields = ("description",)
