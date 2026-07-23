from django.contrib import admin

from .models import Customer, CustomerPayment


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "area", "credit_limit", "is_active", "branch_id")
    list_filter = ("is_active",)
    search_fields = ("name", "phone")


@admin.register(CustomerPayment)
class CustomerPaymentAdmin(admin.ModelAdmin):
    list_display = ("customer", "amount", "payment_date", "payment_method", "recorded_by")
    search_fields = ("customer__name",)
