from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import serializers

from apps.core.utils.xaf import round_xaf
from apps.inventory.models import Product
from apps.sync.models import OutboxEntry
from apps.sync.utils import write_outbox_entry

from .models import HeldSale, Sale, SaleLineItem
from .services import resolve_unit_price


class SaleLineItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = SaleLineItem
        fields = [
            "id", "product", "product_name", "quantity",
            "catalogue_price", "actual_price", "variance",
            "variance_approved_by", "line_total",
        ]
        read_only_fields = fields


class SaleLineItemInputSerializer(serializers.Serializer):
    """Write-side shape for a POS cart line — see SaleSerializer.create()."""

    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    quantity = serializers.IntegerField(min_value=1)


class SaleSerializer(serializers.ModelSerializer):
    line_items = SaleLineItemSerializer(many=True, read_only=True)
    items = SaleLineItemInputSerializer(many=True, write_only=True)
    cashier_name = serializers.CharField(source="cashier.name", read_only=True)

    class Meta:
        model = Sale
        fields = [
            "id", "reference", "cashier", "cashier_name", "payment_method",
            "momo_reference", "momo_confirmed", "subtotal", "tax_amount",
            "total_amount", "amount_tendered", "status", "voided_by",
            "void_reason", "voided_at", "line_items", "items", "created_at",
        ]
        read_only_fields = [
            "id", "reference", "cashier", "cashier_name", "subtotal",
            "tax_amount", "total_amount", "status", "voided_by",
            "void_reason", "voided_at", "line_items", "created_at",
        ]

    def validate(self, attrs):
        payment_method = attrs.get("payment_method")
        if payment_method in (Sale.MTN_MOMO, Sale.ORANGE_MONEY):
            if not attrs.get("momo_reference"):
                raise serializers.ValidationError(
                    {"momo_reference": "Required for Mobile Money payments."}
                )
            if not attrs.get("momo_confirmed"):
                raise serializers.ValidationError(
                    {"momo_confirmed": "Must be confirmed on phone before completing the sale."}
                )
        if not attrs.get("items"):
            raise serializers.ValidationError({"items": "A sale must have at least one line item."})
        return attrs

    def create(self, validated_data):
        items_data = validated_data.pop("items")
        # Sale.reference is unique at the DB level — two concurrent
        # writers can compute the same "next" reference, in which case
        # the loser's INSERT raises IntegrityError and the attempt is
        # retried with a freshly computed reference. The whole atomic
        # block re-runs in full (stock checks included) because an
        # IntegrityError poisons the open transaction.
        for attempt in range(5):
            try:
                return self._create_once(validated_data, items_data)
            except IntegrityError:
                if attempt == 4:
                    raise

    def _next_reference(self, year, branch_code):
        """
        Highest existing sequence for this branch and `year`, plus one.

        Format is BLD-<branch_code>-<year>-<seq> (Phase 2 design §8.1).
        The branch code is what makes references unique across a
        multi-branch cloud: without it every branch independently
        generates BLD-2026-0001 and only the first push survives the
        unique constraint.

        Reads the most recently *created* reference rather than
        count()-ing rows — count-then-format collides whenever two sales
        race and stays wrong forever once any sequence number is skipped.
        created_at ordering also keeps working past sale 9999, where
        zero-padded string ordering of the reference itself would not.

        The sequence stays per-branch-per-year, so a branch never needs
        to coordinate with the cloud (or any other branch) to allocate
        its next number — which is what keeps sale creation fully
        offline-capable.
        """
        prefix = f"BLD-{branch_code}-{year}-"
        last = (
            Sale.all_objects.filter(reference__startswith=prefix)
            .order_by("-created_at")
            .values_list("reference", flat=True)
            .first()
        )
        last_seq = int(last.rsplit("-", 1)[1]) if last else 0
        return f"{prefix}{last_seq + 1:04d}"

    def _create_once(self, validated_data, items_data):
        request = self.context["request"]
        branch_id = request.branch_id

        with transaction.atomic():
            line_items_payload = []
            subtotal = 0

            for item in items_data:
                # select_for_update — same locking pattern as
                # inventory's StockAdjustmentSerializer.create().
                product = Product.objects.select_for_update().get(pk=item["product"].pk)
                quantity = item["quantity"]

                if product.stock_level < quantity:
                    raise serializers.ValidationError(
                        {
                            "items": (
                                f"Insufficient stock for {product.name} "
                                f"(have {product.stock_level}, need {quantity})."
                            )
                        }
                    )

                unit_price = resolve_unit_price(product, branch_id, quantity)
                line_total = round_xaf(unit_price * quantity)

                line_items_payload.append(
                    {
                        "product": product,
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "line_total": line_total,
                    }
                )
                subtotal += line_total

            tax_amount = 0  # no tax in Phase 1 — receipt shows "Tax (0%)"
            total_amount = subtotal + tax_amount

            # Branch code comes from the cashier's own Branch row, not
            # settings.BRANCH_ID -- Phase 2 §2.3 moves branch identity
            # onto the Branch record, and the cashier is always a member
            # of exactly the branch this sale belongs to.
            reference = self._next_reference(timezone.now().year, request.user.branch.code)

            sale = Sale.objects.create(
                branch_id=branch_id,
                cashier=request.user,
                reference=reference,
                subtotal=subtotal,
                tax_amount=tax_amount,
                total_amount=total_amount,
                **validated_data,
            )

            for payload in line_items_payload:
                SaleLineItem.objects.create(
                    branch_id=branch_id,
                    sale=sale,
                    product=payload["product"],
                    quantity=payload["quantity"],
                    catalogue_price=payload["unit_price"],
                    actual_price=payload["unit_price"],
                    variance=0,
                    line_total=payload["line_total"],
                )
                # updated_at/version included so the product row's
                # optimistic-concurrency fields move with every stock
                # write — same trio as StockAdjustmentSerializer.create().
                payload["product"].stock_level = F("stock_level") - payload["quantity"]
                payload["product"].save(update_fields=["stock_level", "updated_at", "version"])

            write_outbox_entry(instance=sale, operation=OutboxEntry.INSERT, branch_id=branch_id)

        sale.refresh_from_db()
        return sale


class VoidSaleSerializer(serializers.Serializer):
    void_reason = serializers.CharField(allow_blank=False)

    def save(self, **kwargs):
        sale = self.context["sale"]
        request = self.context["request"]

        if sale.status == Sale.VOIDED:
            raise serializers.ValidationError("This sale has already been voided.")

        with transaction.atomic():
            for line_item in sale.line_items.select_related("product"):
                # Instance save(), not queryset .update() — .update()
                # bypasses BaseModel.save(), so version/updated_at
                # wouldn't move with the stock write like they do at
                # every other stock-mutation site.
                locked_product = Product.objects.select_for_update().get(pk=line_item.product_id)
                locked_product.stock_level = F("stock_level") + line_item.quantity
                locked_product.save(update_fields=["stock_level", "updated_at", "version"])

            sale.status = Sale.VOIDED
            sale.voided_by = request.user
            sale.void_reason = self.validated_data["void_reason"]
            sale.voided_at = timezone.now()
            sale.save(
                update_fields=["status", "voided_by", "void_reason", "voided_at", "updated_at", "version"]
            )

            write_outbox_entry(instance=sale, operation=OutboxEntry.UPDATE, branch_id=sale.branch_id)

        return sale


class HeldSaleSerializer(serializers.ModelSerializer):
    held_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = HeldSale
        fields = ["id", "cashier", "label", "cart_data", "held_at", "created_at"]
        read_only_fields = ["id", "cashier", "held_at", "created_at"]

    def create(self, validated_data):
        request = self.context["request"]
        return HeldSale.objects.create(
            branch_id=request.branch_id,
            cashier=request.user,
            **validated_data,
        )
