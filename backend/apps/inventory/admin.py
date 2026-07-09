from django.contrib import admin

from .models import BranchPriceOverride, Category, Product, ProductTemplate, StockAdjustment


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "branch_id", "sort_order")
    list_filter = ("branch_id",)
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "branch_id", "category", "retail_price", "stock_level", "is_active", "source")
    list_filter = ("branch_id", "category", "is_active", "source")
    search_fields = ("name", "description")


@admin.register(BranchPriceOverride)
class BranchPriceOverrideAdmin(admin.ModelAdmin):
    list_display = ("product", "branch_id", "retail_price_override", "bulk_price_override", "set_by")
    list_filter = ("branch_id",)


@admin.register(StockAdjustment)
class StockAdjustmentAdmin(admin.ModelAdmin):
    """Read-only in admin too — see model docstring: never edited after creation."""

    list_display = ("product", "branch_id", "adjustment_type", "quantity", "stock_before", "stock_after", "adjusted_by", "created_at")
    list_filter = ("branch_id", "adjustment_type")
    readonly_fields = [f.name for f in StockAdjustment._meta.fields]

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ProductTemplate)
class ProductTemplateAdmin(admin.ModelAdmin):
    list_display = ("key", "name", "fixture_name")
