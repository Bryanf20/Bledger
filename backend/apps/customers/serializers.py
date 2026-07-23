"""
Customers & credit serializers (Phase 2 design §4).

RecordCustomerPaymentSerializer follows the same plain-Serializer-with-a
-save() pattern as suppliers.RecordPurchasePaymentSerializer and
sales.VoidSaleSerializer — a narrow action endpoint, not a general PATCH,
since a payment is an append-only financial record.

Balance is always computed via services.customer_balance(), never read
from a stored field (§4.3).
"""
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.sync.models import OutboxEntry
from apps.sync.utils import write_outbox_entry

from .models import Customer, CustomerPayment
from .services import aging_buckets, customer_balance


class CustomerPaymentSerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.CharField(source="recorded_by.name", read_only=True, default=None)

    class Meta:
        model = CustomerPayment
        fields = [
            "id", "amount", "payment_date", "payment_method",
            "recorded_by", "recorded_by_name", "note", "created_at",
        ]
        read_only_fields = fields


class CustomerSerializer(serializers.ModelSerializer):
    # Derived (§4.3) — one aggregate per customer. Fine at SME scale; add
    # a materialised balance only if profiling ever demands it.
    balance = serializers.SerializerMethodField()
    payments = CustomerPaymentSerializer(many=True, read_only=True)

    class Meta:
        model = Customer
        fields = [
            "id", "name", "phone", "area", "notes", "is_active",
            "credit_limit", "balance", "payments", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "balance", "payments", "created_at", "updated_at"]

    def get_balance(self, customer):
        return customer_balance(customer)


class RecordCustomerPaymentSerializer(serializers.Serializer):
    """POST /customers/{id}/record-payment/ { amount, payment_date?, payment_method?, note? }."""

    amount = serializers.IntegerField(min_value=1)
    payment_date = serializers.DateField(required=False)
    payment_method = serializers.CharField(required=False, allow_blank=True, default="cash")
    note = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        customer = self.context["customer"]
        balance = customer_balance(customer)
        if balance <= 0:
            raise serializers.ValidationError("This customer has no outstanding balance.")
        if attrs["amount"] > balance:
            raise serializers.ValidationError(
                f"Amount exceeds the balance owed ({balance} XAF)."
            )
        return attrs

    def save(self, **kwargs):
        request = self.context["request"]
        customer = self.context["customer"]
        with transaction.atomic():
            payment = CustomerPayment.objects.create(
                branch_id=customer.branch_id,
                customer=customer,
                amount=self.validated_data["amount"],
                payment_date=self.validated_data.get("payment_date") or timezone.localdate(),
                payment_method=self.validated_data.get("payment_method") or "cash",
                recorded_by=request.user,
                note=self.validated_data.get("note", ""),
            )
            write_outbox_entry(
                instance=payment, operation=OutboxEntry.INSERT, branch_id=customer.branch_id
            )
        return payment


class AgedDebtSerializer(serializers.Serializer):
    """One row of the aged-debt report (§4.5)."""

    customer_id = serializers.UUIDField()
    name = serializers.CharField()
    phone = serializers.CharField()
    balance = serializers.IntegerField()
    bucket_0_30 = serializers.IntegerField()
    bucket_31_60 = serializers.IntegerField()
    bucket_61_plus = serializers.IntegerField()
