from django.contrib import admin

from .models import Purchase, PurchaseLineItem, Supplier


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "branch_id", "phone", "area", "is_active")
    list_filter = ("branch_id", "is_active")
    search_fields = ("name", "phone")


class PurchaseLineItemInline(admin.TabularInline):
    model = PurchaseLineItem
    extra = 0
    readonly_fields = [f.name for f in PurchaseLineItem._meta.fields]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    """
    Read-only in admin, same principle as sales.SaleAdmin: once a
    purchase has updated the stock ledger, editing it here would leave
    Product.stock_level silently wrong.
    """
    list_display = ("supplier", "branch_id", "purchase_date", "total_amount", "amount_paid", "payment_status", "recorded_by")
    list_filter = ("branch_id", "payment_status")
    readonly_fields = [f.name for f in Purchase._meta.fields]
    inlines = [PurchaseLineItemInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
    