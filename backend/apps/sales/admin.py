from django.contrib import admin

from .models import HeldSale, Sale, SaleLineItem


class SaleLineItemInline(admin.TabularInline):
    model = SaleLineItem
    extra = 0
    readonly_fields = [f.name for f in SaleLineItem._meta.fields]
    can_delete = False


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ["reference", "branch_id", "cashier", "payment_method", "status", "total_amount", "created_at"]
    list_filter = ["status", "payment_method", "branch_id"]
    search_fields = ["reference"]
    inlines = [SaleLineItemInline]
    readonly_fields = [f.name for f in Sale._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(HeldSale)
class HeldSaleAdmin(admin.ModelAdmin):
    list_display = ["cashier", "label", "branch_id", "created_at"]
