"""
Suppliers & Purchases serializers.

PurchaseSerializer.create() follows the same select_for_update() +
single-transaction pattern as inventory.StockAdjustmentSerializer and
sales.SaleSerializer: every line item locks its Product row, bumps
stock_level via F(), and the whole Purchase + line items + outbox
write happens atomically. Unlike a Sale, a Purchase *increments* stock
rather than decrementing it — there's no "insufficient stock" check to
make.

Any amount_paid supplied at creation time now ALSO creates the first
PurchasePayment row (added this session, right after the ledger itself
was introduced) -- without this, a purchase recorded with an upfront
partial payment would set payment_status="partial" but leave the
payments list empty, which is exactly the inconsistency
PurchaseDetailPanel's "Payments" section would otherwise surface.
amount_paid/payment_status stay the source of truth for reads (same
denormalized-running-total principle as before), but the ledger is now
complete from the moment a purchase is first recorded, not just for
installments added afterward via record-payment.

RecordPurchasePaymentSerializer follows
apps.sales.serializers.VoidSaleSerializer's pattern instead: a plain
Serializer (not ModelSerializer) whose save() does the actual work,
backing a narrow action endpoint (PurchaseViewSet.record_payment())
rather than a general PATCH. See models.py's module docstring for why
Purchase needed this instead of reopening it to edits.
"""
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import serializers

from apps.inventory.models import Product
from apps.inventory.services import weighted_average_cost
from apps.sync.models import OutboxEntry
from apps.sync.utils import write_outbox_entry

from .models import Purchase, PurchaseLineItem, PurchasePayment, Supplier


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
    # Snapshotted name (§7A.1) with a fallback for pre-snapshot rows.
    product_name = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseLineItem
        fields = ["id", "product", "product_name", "quantity", "unit_cost", "line_total"]
        read_only_fields = fields

    def get_product_name(self, obj):
        return obj.product_name or obj.product.name


class PurchaseLineItemInputSerializer(serializers.Serializer):
    """Write-side shape for one restock line — see PurchaseSerializer.create()."""
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    quantity = serializers.IntegerField(min_value=1)
    unit_cost = serializers.IntegerField(min_value=0)


class PurchasePaymentSerializer(serializers.ModelSerializer):
    """
    Read-only nested representation -- shown in PurchaseSerializer's
    `payments` list so the frontend can render a payment history per
    purchase without a separate endpoint. Written only via
    PurchaseSerializer.create() (the initial amount_paid, if any) and
    RecordPurchasePaymentSerializer (every installment after that) --
    never directly.
    """
    recorded_by_name = serializers.CharField(source="recorded_by.name", read_only=True, default=None)

    class Meta:
        model = PurchasePayment
        fields = ["id", "amount", "payment_date", "recorded_by", "recorded_by_name", "note", "created_at"]
        read_only_fields = fields


class PurchaseSerializer(serializers.ModelSerializer):
    line_items = PurchaseLineItemSerializer(many=True, read_only=True)
    items = PurchaseLineItemInputSerializer(many=True, write_only=True)
    payments = PurchasePaymentSerializer(many=True, read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    recorded_by_name = serializers.CharField(source="recorded_by.name", read_only=True)
    balance_due = serializers.SerializerMethodField()

    class Meta:
        model = Purchase
        fields = [
            "id", "supplier", "supplier_name", "purchase_date",
            "total_amount", "amount_paid", "payment_status", "balance_due",
            "recorded_by", "recorded_by_name", "line_items", "items", "payments",
            "created_at",
        ]
        read_only_fields = [
            "id", "total_amount", "payment_status", "balance_due", "recorded_by",
            "recorded_by_name", "line_items", "payments", "created_at",
        ]

    def get_balance_due(self, purchase):
        return purchase.balance_due

    def validate(self, attrs):
        if not attrs.get("items"):
            raise serializers.ValidationError({"items": "A purchase must have at least one line item."})
        if attrs.get("amount_paid", 0) < 0:
            raise serializers.ValidationError({"amount_paid": "Cannot be negative."})
        # Server-side twin of the frontend's disabled "+ Record purchase"
        # button for inactive suppliers -- deactivation means "we've
        # stopped buying from them", so new purchases are rejected until
        # the supplier is reactivated (PATCH is_active=true).
        supplier = attrs.get("supplier")
        if supplier is not None and not supplier.is_active:
            raise serializers.ValidationError(
                {"supplier": "This supplier is deactivated — reactivate it before recording a purchase."}
            )
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
                product = payload["product"]
                PurchaseLineItem.objects.create(
                    branch_id=branch_id,
                    purchase=purchase,
                    product=product,
                    # Snapshot the name at purchase time (§7A.1).
                    product_name=product.name,
                    quantity=payload["quantity"],
                    unit_cost=payload["unit_cost"],
                    line_total=payload["line_total"],
                )
                # Recompute weighted-average cost (§7A.5) using the
                # pre-purchase stock and average — must happen BEFORE
                # stock_level becomes an F() expression below. A purchase
                # is the one event that establishes/moves cost, so it also
                # records last_cost and flips cost_is_set on.
                #
                # If the product had no cost basis yet (cost_is_set=False),
                # this purchase ESTABLISHES it: the incoming cost becomes
                # the average outright. Blending against the phantom
                # average_cost=0 of existing unknown-cost stock would
                # understate it badly (50 opening units + 50 bought at
                # 3800 would read 1900, not 3800).
                if not product.cost_is_set:
                    product.average_cost = payload["unit_cost"]
                else:
                    product.average_cost = weighted_average_cost(
                        product.stock_level, product.average_cost,
                        payload["quantity"], payload["unit_cost"],
                    )
                product.last_cost = payload["unit_cost"]
                product.cost_is_set = True
                # updated_at/version included so the product row's
                # optimistic-concurrency fields move with every stock
                # write — same trio as StockAdjustmentSerializer.create().
                product.stock_level = F("stock_level") + payload["quantity"]
                product.save(update_fields=[
                    "stock_level", "average_cost", "last_cost", "cost_is_set",
                    "updated_at", "version",
                ])

            # The amount paid at the moment of recording IS a payment --
            # give it its own PurchasePayment row so the ledger is
            # complete from the start, not just for installments added
            # later via record-payment. payment_date defaults to the
            # purchase's own date (not "today") since that's when this
            # money actually changed hands, as far as the record goes.
            if amount_paid > 0:
                initial_payment = PurchasePayment.objects.create(
                    branch_id=branch_id,
                    purchase=purchase,
                    amount=amount_paid,
                    payment_date=validated_data["purchase_date"],
                    recorded_by=request.user,
                    note="Paid at time of purchase",
                )
                write_outbox_entry(instance=initial_payment, operation=OutboxEntry.INSERT, branch_id=branch_id)

            write_outbox_entry(instance=purchase, operation=OutboxEntry.INSERT, branch_id=branch_id)

        purchase.refresh_from_db()
        return purchase


class RecordPurchasePaymentSerializer(serializers.Serializer):
    """
    Write-side shape for POST /purchases/{id}/record-payment/ -- the
    one purpose-built mutation on an otherwise-immutable Purchase
    (PurchaseViewSet.http_method_names has no PATCH/DELETE), mirroring
    Sale's /void/ action rather than opening a general PATCH route.
    See models.py's module docstring for the full reasoning.
    """
    amount = serializers.IntegerField(min_value=1)
    payment_date = serializers.DateField(required=False)
    note = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        purchase = self.context["purchase"]
        if purchase.balance_due <= 0:
            raise serializers.ValidationError("This purchase is already fully paid.")
        if attrs["amount"] > purchase.balance_due:
            raise serializers.ValidationError(
                f"Amount exceeds the remaining balance ({purchase.balance_due} XAF owed)."
            )
        return attrs

    def save(self, **kwargs):
        request = self.context["request"]
        amount = self.validated_data["amount"]
        payment_date = self.validated_data.get("payment_date") or timezone.localdate()
        note = self.validated_data.get("note", "")

        with transaction.atomic():
            # Re-fetch and lock under the transaction -- the validate()
            # check above ran against the `purchase` passed in from the
            # view, fetched before this transaction started. Same race
            # guard every other select_for_update() call site in this
            # project uses (e.g. StockAdjustmentSerializer.create()).
            locked_purchase = Purchase.objects.select_for_update().get(pk=self.context["purchase"].pk)
            if amount > locked_purchase.balance_due:
                raise serializers.ValidationError(
                    f"Amount exceeds the remaining balance ({locked_purchase.balance_due} XAF owed)."
                )

            payment = PurchasePayment.objects.create(
                branch_id=locked_purchase.branch_id,
                purchase=locked_purchase,
                amount=amount,
                payment_date=payment_date,
                recorded_by=request.user,
                note=note,
            )

            locked_purchase.amount_paid = F("amount_paid") + amount
            locked_purchase.save(update_fields=["amount_paid", "updated_at", "version"])
            locked_purchase.refresh_from_db()

            if locked_purchase.amount_paid >= locked_purchase.total_amount:
                new_status = Purchase.PAID
            elif locked_purchase.amount_paid > 0:
                new_status = Purchase.PARTIAL
            else:
                new_status = Purchase.CREDIT
            if new_status != locked_purchase.payment_status:
                locked_purchase.payment_status = new_status
                locked_purchase.save(update_fields=["payment_status", "updated_at", "version"])

            write_outbox_entry(instance=payment, operation=OutboxEntry.INSERT, branch_id=locked_purchase.branch_id)
            write_outbox_entry(instance=locked_purchase, operation=OutboxEntry.UPDATE, branch_id=locked_purchase.branch_id)

        return locked_purchase
    