from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import serializers

from apps.auth_users.approvals import (
    PURPOSE_CREDIT_OVERRIDE,
    PURPOSE_PRICE_VARIANCE,
    ApprovalError,
    verify_approval_token,
)
from apps.auth_users.models import BledgerUser
from apps.core.utils.xaf import round_xaf
from apps.customers.models import Customer, CustomerPayment
from apps.customers.services import customer_balance
from apps.inventory.models import Product
from apps.inventory.services import resolve_price_bounds, weighted_average_cost
from apps.sync.models import OutboxEntry
from apps.sync.utils import write_outbox_entry

from .models import HeldSale, Sale, SaleLineItem
from .services import price_needs_approval, resolve_unit_price


class SaleLineItemSerializer(serializers.ModelSerializer):
    # Prefer the name snapshotted at sale time (§7A.1); fall back to the
    # live product for rows created before snapshotting existed.
    # unit_cost_at_sale is deliberately NOT exposed here — cost is
    # financial data cashiers don't see (same reasoning as suppliers
    # being manager+); margin reporting (step 8) reads it server-side.
    product_name = serializers.SerializerMethodField()

    class Meta:
        model = SaleLineItem
        fields = [
            "id", "product", "product_name", "quantity",
            "catalogue_price", "actual_price", "variance",
            "variance_approved_by", "line_total",
            # is_brokered / source_note are not COGS, so they're safe to
            # show (a cashier marked the line and wrote the note); the
            # external cost lives in unit_cost_at_sale, which stays hidden.
            "is_brokered", "source_note",
        ]
        read_only_fields = fields

    def get_product_name(self, obj):
        return obj.product_name or obj.product.name


class SaleLineItemInputSerializer(serializers.Serializer):
    """Write-side shape for a POS cart line — see SaleSerializer.create()."""

    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    quantity = serializers.IntegerField(min_value=1)
    # Negotiated selling price per unit (§3.2). Optional — omit for a
    # normal sale at the catalogue/branch price. When it differs from the
    # resolved catalogue price by more than the allowed band, the sale
    # needs a manager approval token (see SaleSerializer).
    actual_price = serializers.IntegerField(min_value=0, required=False)
    # Brokered line (§7B.1): sourced externally, moves no stock. When set,
    # external_cost (what was paid the outside source) is required and is
    # recorded as the line's cost-of-goods-sold.
    is_brokered = serializers.BooleanField(required=False, default=False)
    external_cost = serializers.IntegerField(min_value=0, required=False)
    source_note = serializers.CharField(
        max_length=150, required=False, allow_blank=True, default=""
    )

    def validate(self, attrs):
        if attrs.get("is_brokered") and attrs.get("external_cost") is None:
            raise serializers.ValidationError(
                {"external_cost": "Enter what you paid the source for a brokered item."}
            )
        return attrs


class SaleSerializer(serializers.ModelSerializer):
    line_items = SaleLineItemSerializer(many=True, read_only=True)
    items = SaleLineItemInputSerializer(many=True, write_only=True)
    cashier_name = serializers.CharField(source="cashier.name", read_only=True)
    # A one-shot manager-approval token (from POST /auth/verify-pin/ with
    # purpose "price_variance") authorising any lines whose negotiated
    # price falls outside the allowed band (§3.2). Absent for a normal
    # sale; required the moment any line breaches its bounds.
    approval_token = serializers.CharField(write_only=True, required=False, allow_blank=True)
    # A separate one-shot token (purpose "credit_override") authorising a
    # credit sale that would push the customer past their credit_limit
    # (§4.2). Distinct from approval_token because one sale can, in
    # principle, need both a price approval and a credit approval.
    credit_approval_token = serializers.CharField(write_only=True, required=False, allow_blank=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True, default=None)

    class Meta:
        model = Sale
        fields = [
            "id", "reference", "cashier", "cashier_name", "customer",
            "customer_name", "payment_method",
            "momo_reference", "momo_confirmed", "subtotal", "tax_amount",
            "total_amount", "amount_tendered", "status", "voided_by",
            "void_reason", "voided_at", "line_items", "items", "approval_token",
            "credit_approval_token", "created_at",
        ]
        read_only_fields = [
            "id", "reference", "cashier", "cashier_name", "customer_name",
            "subtotal", "tax_amount", "total_amount", "status", "voided_by",
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
        if attrs.get("payment_method") == Sale.CREDIT and attrs.get("customer") is None:
            raise serializers.ValidationError(
                {"customer": "A credit sale must be attached to a customer."}
            )
        return attrs

    def create(self, validated_data):
        items_data = validated_data.pop("items")
        # Popped here so they aren't forwarded into Sale.objects.create() —
        # these are authorisation inputs, not Sale fields.
        approval_token = validated_data.pop("approval_token", "")
        credit_approval_token = validated_data.pop("credit_approval_token", "")
        self._credit_approval_token = credit_approval_token
        # Sale.reference is unique at the DB level — two concurrent
        # writers can compute the same "next" reference, in which case
        # the loser's INSERT raises IntegrityError and the attempt is
        # retried with a freshly computed reference. The whole atomic
        # block re-runs in full (stock checks included) because an
        # IntegrityError poisons the open transaction.
        for attempt in range(5):
            try:
                return self._create_once(validated_data, items_data, approval_token)
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

    def _create_once(self, validated_data, items_data, approval_token):
        request = self.context["request"]
        branch_id = request.branch_id

        with transaction.atomic():
            line_items_payload = []
            subtotal = 0

            for item in items_data:
                quantity = item["quantity"]
                is_brokered = item.get("is_brokered", False)

                if is_brokered:
                    # Sourced externally — the item never entered this
                    # shop's inventory, so no stock check and no lock (we
                    # won't write the product row). It stays referenced for
                    # its name and catalogue price.
                    product = Product.objects.get(pk=item["product"].pk)
                else:
                    # select_for_update — same locking pattern as
                    # inventory's StockAdjustmentSerializer.create().
                    product = Product.objects.select_for_update().get(pk=item["product"].pk)
                    if product.stock_level < quantity:
                        raise serializers.ValidationError(
                            {
                                "items": (
                                    f"Insufficient stock for {product.name} "
                                    f"(have {product.stock_level}, need {quantity})."
                                )
                            }
                        )

                # Catalogue price is ALWAYS resolved server-side and never
                # trusted from the client (§3.3). actual_price is the
                # cashier's negotiated price; absent means "at catalogue".
                catalogue_price = resolve_unit_price(product, branch_id, quantity)
                actual_price = item.get("actual_price")
                if actual_price is None:
                    actual_price = catalogue_price
                variance = actual_price - catalogue_price

                # A price outside the product's allowed band needs a
                # manager's approval (§3.2). Bounds resolve product →
                # category → business default.
                floor_pct, ceiling_pct = resolve_price_bounds(product)
                needs_approval = price_needs_approval(
                    catalogue_price, actual_price, floor_pct, ceiling_pct
                )

                line_total = round_xaf(actual_price * quantity)

                line_items_payload.append(
                    {
                        "product": product,
                        "quantity": quantity,
                        "catalogue_price": catalogue_price,
                        "actual_price": actual_price,
                        "variance": variance,
                        "needs_approval": needs_approval,
                        "line_total": line_total,
                        "is_brokered": is_brokered,
                        "external_cost": item.get("external_cost", 0),
                        "source_note": item.get("source_note", ""),
                    }
                )
                subtotal += line_total

            # If any line breached its bounds, the whole sale needs a valid
            # manager approval token (§3.3 step 5). Without it — or with an
            # expired/tampered/wrong-purpose one — the sale is rejected.
            # This is the actual control; client-side bounds are only UX.
            approver = None
            if any(p["needs_approval"] for p in line_items_payload):
                try:
                    approver_id = verify_approval_token(
                        approval_token, purpose=PURPOSE_PRICE_VARIANCE
                    )
                except ApprovalError as exc:
                    raise serializers.ValidationError({"approval_token": str(exc)})
                approver = BledgerUser.objects.filter(pk=approver_id, is_active=True).first()
                if approver is None:
                    raise serializers.ValidationError(
                        {"approval_token": "The approving manager could not be found."}
                    )

            tax_amount = 0  # no tax in Phase 1 — receipt shows "Tax (0%)"
            total_amount = subtotal + tax_amount

            # Credit-limit enforcement (§4.2). The amount going on account
            # is the total minus any upfront cash (amount_tendered). If it
            # would push the customer past their credit_limit, the sale
            # needs a manager credit-override token — the actual control,
            # server-side.
            customer = validated_data.get("customer")
            if validated_data.get("payment_method") == Sale.CREDIT:
                upfront = validated_data.get("amount_tendered") or 0
                going_on_credit = max(total_amount - upfront, 0)
                projected_balance = max(customer_balance(customer), 0) + going_on_credit
                if projected_balance > customer.credit_limit:
                    try:
                        credit_approver_id = verify_approval_token(
                            self._credit_approval_token, purpose=PURPOSE_CREDIT_OVERRIDE
                        )
                    except ApprovalError as exc:
                        raise serializers.ValidationError({"credit_approval_token": str(exc)})
                    if not BledgerUser.objects.filter(pk=credit_approver_id, is_active=True).exists():
                        raise serializers.ValidationError(
                            {"credit_approval_token": "The approving manager could not be found."}
                        )

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
                product = payload["product"]
                is_brokered = payload["is_brokered"]
                SaleLineItem.objects.create(
                    branch_id=branch_id,
                    sale=sale,
                    product=product,
                    # Snapshot name (§7A.1) and cost-of-goods-sold (§7A.5)
                    # at sale time, exactly as the price fields are
                    # snapshotted, so history stays correct as the product
                    # is renamed or its average cost moves. For a brokered
                    # line the COGS is the external cost paid to the source
                    # (§7B.1); otherwise it's the product's average cost
                    # (0 when never set — reporting treats that as unknown).
                    product_name=product.name,
                    quantity=payload["quantity"],
                    catalogue_price=payload["catalogue_price"],
                    actual_price=payload["actual_price"],
                    variance=payload["variance"],
                    # The approver is recorded only on the lines that
                    # actually breached their bounds (§3.3); within-bounds
                    # haggling is free and needs no approver.
                    variance_approved_by=(approver if payload["needs_approval"] else None),
                    unit_cost_at_sale=(
                        payload["external_cost"] if is_brokered else product.average_cost
                    ),
                    is_brokered=is_brokered,
                    source_note=payload["source_note"],
                    line_total=payload["line_total"],
                )
                # A brokered line moves no stock — the item never entered
                # inventory. A normal sale decrements stock; selling does
                # NOT change average_cost (removing units at the average
                # leaves the rest costing the same).
                if not is_brokered:
                    product.stock_level = F("stock_level") - payload["quantity"]
                    product.save(update_fields=["stock_level", "updated_at", "version"])

            # Upfront cash on a credit sale becomes a CustomerPayment, so
            # the customer's derived balance nets it immediately (§4.1) —
            # otherwise the full total would show as owed. Only for credit;
            # for a cash sale amount_tendered is just change-making info.
            if validated_data.get("payment_method") == Sale.CREDIT:
                upfront = validated_data.get("amount_tendered") or 0
                if upfront > 0:
                    payment = CustomerPayment.objects.create(
                        branch_id=branch_id,
                        customer=customer,
                        amount=min(upfront, total_amount),
                        payment_date=timezone.localdate(),
                        payment_method=Sale.CASH,
                        recorded_by=request.user,
                        note=f"Paid at time of credit sale {reference}",
                    )
                    write_outbox_entry(
                        instance=payment, operation=OutboxEntry.INSERT, branch_id=branch_id
                    )

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
                # A brokered line never moved stock and was never part of
                # inventory (§7B.1), so voiding it must NOT restore stock
                # or recompute average_cost — doing so would invent
                # phantom units and corrupt the cost basis. Skip it
                # entirely; the sale row itself still flips to VOIDED below.
                if line_item.is_brokered:
                    continue

                # Instance save(), not queryset .update() — .update()
                # bypasses BaseModel.save(), so version/updated_at
                # wouldn't move with the stock write like they do at
                # every other stock-mutation site.
                locked_product = Product.objects.select_for_update().get(pk=line_item.product_id)

                # Restore the cost basis "as if the sale never happened":
                # the units return at the cost they left at
                # (unit_cost_at_sale), and the average is recomputed over
                # the restored total. Using the *current* average instead
                # would let a void after an intervening purchase — which
                # moved the average — drift it on every void/resell cycle
                # (§7A.5). A 0 snapshot (pre-cost-tracking sale, or a
                # cost-unknown product) means "no basis to restore", so
                # leave the average untouched and just add the stock back.
                if line_item.unit_cost_at_sale > 0:
                    locked_product.average_cost = weighted_average_cost(
                        locked_product.stock_level, locked_product.average_cost,
                        line_item.quantity, line_item.unit_cost_at_sale,
                    )
                locked_product.stock_level = F("stock_level") + line_item.quantity
                locked_product.save(update_fields=[
                    "stock_level", "average_cost", "updated_at", "version",
                ])

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
