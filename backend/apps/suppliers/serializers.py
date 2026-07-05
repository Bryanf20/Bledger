"""
Suppliers & Purchases serializers.

PurchaseSerializer.create() follows the same select_for_update() +
single-transaction pattern as inventory.StockAdjustmentSerializer and
sales.SaleSerializer: every line item locks its Product row, bumps
stock_level via F(), and the whole Purchase + line items + outbox
write happens atomically. Unlike a Sale, a Purchase *increments* stock
rather than decrementing it — there's no "insufficient stock" check to
make.
"""
from django.db import transaction
from django.db.models import F
from rest_framework import serializers

from apps.inventory.models import Product
from apps.sync.models import OutboxEntry
from apps.sync.utils import write_outbox_entry

from .models import Purchase, PurchaseLineItem, Supplier


class SupplierSerializer(serializers.ModelSerializer):
    """
    purchase_count / total_spent (API E.4) are read from queryset
    annotations (SupplierViewSet.get_queryset()) rather than computed
    here per-instance — annotating once on the queryset avoids an N+1
    aggregate query per supplier in a list response. The
    getattr(..., default) fallback keeps this serializer safe to reuse
    anywhere the annotations aren't present (e.g. a bare
    Supplier.objects.create() in a test).
    """

    purchase_count = serializers.SerializerMethodField()
    total_spent = serializers.SerializerMethodField()

    class Meta:
        model = Supplier
        fields = [
            "id", "name", "phone", "area", "notes", "is_active",
            "purchase_count", "total_spent", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "purchase_count", "total_spent", "created_at", "updated_at"]

    def get_purchase_count(self, supplier):
        return getattr(supplier, "purchase_count", 0) or 0

    def get_total_spent(self, supplier):
        return getattr(supplier, "total_spent", 0) or 0


class PurchaseLineItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = PurchaseLineItem
        fields = ["id", "product", "product_name", "quantity", "unit_cost", "line_total"]
        read_only_fields = fields


class PurchaseLineItemInputSerializer(serializers.Serializer):
    """Write-side shape for one restock line — see PurchaseSerializer.create()."""

    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    quantity = serializers.IntegerField(min_value=1)
    unit_cost = serializers.IntegerField(min_value=0)


class PurchaseSerializer(serializers.ModelSerializer):
    line_items = PurchaseLineItemSerializer(many=True, read_only=True)
    items = PurchaseLineItemInputSerializer(many=True, write_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    recorded_by_name = serializers.CharField(source="recorded_by.name", read_only=True)

    class Meta:
        model = Purchase
        fields = [
            "id", "supplier", "supplier_name", "purchase_date",
            "total_amount", "amount_paid", "payment_status",
            "recorded_by", "recorded_by_name", "line_items", "items",
            "created_at",
        ]
        read_only_fields = [
            "id", "total_amount", "payment_status", "recorded_by",
            "recorded_by_name", "line_items", "created_at",
        ]

    def validate(self, attrs):
        if not attrs.get("items"):
            raise serializers.ValidationError({"items": "A purchase must have at least one line item."})
        if attrs.get("amount_paid", 0) < 0:
            raise serializers.ValidationError({"amount_paid": "Cannot be negative."})
        return attrs

    def create(self, validated_data):
        items_data = validated_data.pop("items")
        request = self.context["request"]
        branch_id = request.branch_id
        amount_paid = validated_data.get("amount_paid", 0)

        with transaction.atomic():
            line_items_payload = []
            total_amount = 0

            for item in items_data:
                # select_for_update — same locking pattern as
                # inventory.StockAdjustmentSerializer.create() and
                # sales.SaleSerializer.create(). No stock-sufficiency
                # check here: a purchase only ever adds stock.
                product = Product.objects.select_for_update().get(pk=item["product"].pk)
                quantity = item["quantity"]
                unit_cost = item["unit_cost"]
                line_total = quantity * unit_cost

                line_items_payload.append(
                    {
                        "product": product,
                        "quantity": quantity,
                        "unit_cost": unit_cost,
                        "line_total": line_total,
                    }
                )
                total_amount += line_total

            if amount_paid <= 0:
                payment_status = Purchase.CREDIT
            elif amount_paid < total_amount:
                payment_status = Purchase.PARTIAL
            else:
                payment_status = Purchase.PAID

            purchase = Purchase.objects.create(
                branch_id=branch_id,
                recorded_by=request.user,
                total_amount=total_amount,
                payment_status=payment_status,
                **validated_data,
            )

            for payload in line_items_payload:
                PurchaseLineItem.objects.create(
                    branch_id=branch_id,
                    purchase=purchase,
                    product=payload["product"],
                    quantity=payload["quantity"],
                    unit_cost=payload["unit_cost"],
                    line_total=payload["line_total"],
                )
                payload["product"].stock_level = F("stock_level") + payload["quantity"]
                payload["product"].save(update_fields=["stock_level"])

            write_outbox_entry(instance=purchase, operation=OutboxEntry.INSERT, branch_id=branch_id)

        purchase.refresh_from_db()
        return purchase
    