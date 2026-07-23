"""
Inventory serializers.

Product.stock_level only ever moves through StockAdjustmentSerializer.create()
here (and, once built, the suppliers app recording a purchase) — both do
so atomically inside a transaction so stock_before/stock_after snapshots
stay trustworthy for the audit trail.
"""
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.sync.models import OutboxEntry
from apps.sync.utils import write_outbox_entry

from .models import (
    BranchPriceOverride,
    Category,
    Product,
    ProductTemplate,
    StockAdjustment,
)
from .services import resolve_price_bounds


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = [
            "id", "name", "description", "sort_order",
            # Negotiated-pricing bounds for this category (§3.1); null =
            # inherit the business default.
            "discount_floor_pct", "surplus_ceiling_pct",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    stock_status = serializers.CharField(read_only=True)
    # The catalogue/branch-override distinction only bites in Phase 2
    # multi-branch, but the fields are exposed from Phase 1 so the POS
    # frontend never has to special-case "does this branch have an
    # override" — it always reads effective_retail_price /
    # effective_bulk_price (design doc Part D / Feasibility Section 9.3).
    effective_retail_price = serializers.SerializerMethodField()
    effective_bulk_price = serializers.SerializerMethodField()
    # Resolved negotiated-pricing bounds (§3.1) — product → category →
    # business default — so the POS knows each product's allowed
    # discount/surplus band without resolving it client-side.
    effective_discount_floor_pct = serializers.SerializerMethodField()
    effective_surplus_ceiling_pct = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id", "name", "description", "category", "category_name", "unit",
            "retail_price", "bulk_price", "bulk_min_qty",
            "stock_level", "low_stock_threshold", "stock_status",
            "is_active", "source", "barcode",
            # Cost basis (§7A). average_cost is writable (manager+ only,
            # like the rest of product editing) so an owner can seed the
            # cost of opening stock or correct it; normally it's driven by
            # purchases. cost_is_set / last_cost are server-maintained.
            "average_cost", "cost_is_set", "last_cost",
            # Per-product negotiated-pricing bounds (§3.1), writable; null
            # = inherit category/business. Resolved values below.
            "discount_floor_pct", "surplus_ceiling_pct",
            "effective_retail_price", "effective_bulk_price",
            "effective_discount_floor_pct", "effective_surplus_ceiling_pct",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "stock_level", "source", "cost_is_set", "last_cost",
            "created_at", "updated_at",
        ]

    def _bounds(self, product):
        # Load BusinessSettings once per serializer (not per product — a
        # 1000-item POS list would otherwise re-query it every row), and
        # cache the resolved pair per product so both method fields share.
        if not hasattr(self, "_biz_settings"):
            from apps.auth_users.models import BusinessSettings
            self._biz_settings = BusinessSettings.load()
        if not hasattr(product, "_resolved_bounds"):
            product._resolved_bounds = resolve_price_bounds(product, settings_row=self._biz_settings)
        return product._resolved_bounds

    def get_effective_discount_floor_pct(self, product):
        return self._bounds(product)[0]

    def get_effective_surplus_ceiling_pct(self, product):
        return self._bounds(product)[1]

    def validate_barcode(self, value):
        # Empty is always fine (barcode is optional — see the model).
        # When set, it must be unique within the branch. The DB constraint
        # is the real guarantee; this check turns what would otherwise be
        # an IntegrityError 500 into a clean 400 with a useful message.
        value = (value or "").strip()
        if not value:
            return ""
        request = self.context.get("request")
        if request is None:
            return value
        clash = Product.all_objects.filter(
            branch_id=request.branch_id, barcode=value, deleted_at__isnull=True
        )
        if self.instance is not None:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError(
                f"Another product in this branch already uses barcode {value}."
            )
        return value

    def validate(self, attrs):
        bulk_price = attrs.get("bulk_price", getattr(self.instance, "bulk_price", None))
        bulk_min_qty = attrs.get("bulk_min_qty", getattr(self.instance, "bulk_min_qty", None))
        if bool(bulk_price) != bool(bulk_min_qty):
            raise serializers.ValidationError(
                "bulk_price and bulk_min_qty must be set together."
            )
        return attrs

    def _override_for(self, product):
        request = self.context.get("request")
        if request is None:
            return None
        return product.price_overrides.filter(branch_id=request.branch_id).first()

    def get_effective_retail_price(self, product):
        override = self._override_for(product)
        if override and override.retail_price_override is not None:
            return override.retail_price_override
        return product.retail_price

    def get_effective_bulk_price(self, product):
        override = self._override_for(product)
        if override and override.bulk_price_override is not None:
            return override.bulk_price_override
        return product.bulk_price


class BranchPriceOverrideSerializer(serializers.ModelSerializer):
    """
    UPSERT on (product, branch) per API E.2 — create() overwrites any
    existing override for this product on the caller's branch instead of
    raising a uniqueness error, so the frontend never has to know
    whether an override already exists before saving one.
    """

    class Meta:
        model = BranchPriceOverride
        fields = [
            "id", "product", "retail_price_override", "bulk_price_override",
            "bulk_min_qty_override", "set_by", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "set_by", "created_at", "updated_at"]

    def create(self, validated_data):
        request = self.context["request"]
        product = validated_data["product"]
 
        with transaction.atomic():
            override, created = BranchPriceOverride.objects.update_or_create(
                product=product,
                branch_id=request.branch_id,
                defaults={
                    "retail_price_override": validated_data.get("retail_price_override"),
                    "bulk_price_override": validated_data.get("bulk_price_override"),
                    "bulk_min_qty_override": validated_data.get("bulk_min_qty_override"),
                    "set_by": request.user,
                },
            )
            write_outbox_entry(
                instance=override,
                operation=OutboxEntry.INSERT if created else OutboxEntry.UPDATE,
                branch_id=request.branch_id,
            )
        return override


class StockAdjustmentSerializer(serializers.ModelSerializer):
    """
    Read: full audit log (design doc D: "Never deleted — full audit
    trail"). Write: create() applies the adjustment to
    Product.stock_level atomically and snapshots stock_before/after —
    those two fields, plus adjusted_by, are never client-supplied.
    """
    product_name = serializers.CharField(source="product.name", read_only=True)
    # Write-only confirmation that a damage/expiry removal should also be
    # booked as a Losses/Damage expense (§7B.2 / step 8d). The frontend
    # computes the default amount (|qty| × average_cost) and lets the
    # user confirm or edit it — hence "ask each time", the amount is the
    # confirmed value rather than something the server imposes silently.
    book_as_expense = serializers.BooleanField(write_only=True, required=False, default=False)
    expense_amount = serializers.IntegerField(write_only=True, required=False, min_value=0)
    # Read-back so the client can show "booked N XAF" after the fact.
    booked_expense_amount = serializers.SerializerMethodField()

    class Meta:
        model = StockAdjustment
        fields = [
            "id", "product", "product_name", "adjustment_type", "quantity",
            "reason", "adjusted_by", "stock_before", "stock_after", "created_at",
            "book_as_expense", "expense_amount", "booked_expense_amount",
        ]
        read_only_fields = ["id", "adjusted_by", "stock_before", "stock_after", "created_at"]

    def get_booked_expense_amount(self, obj):
        entry = obj.booked_expenses.first() if hasattr(obj, "booked_expenses") else None
        return entry.amount if entry else None

    def validate(self, attrs):
        adj_type = attrs["adjustment_type"]
        quantity = attrs["quantity"]
        if adj_type == "add" and quantity <= 0:
            raise serializers.ValidationError("Quantity must be positive for an 'add' adjustment.")
        if adj_type == "remove" and quantity >= 0:
            raise serializers.ValidationError("Quantity must be negative for a 'remove' adjustment.")
        if not attrs.get("reason", "").strip():
            raise serializers.ValidationError("A reason is required for every stock adjustment.")
        # Booking an expense only makes sense for a removal (damage/expiry);
        # an 'add' or 'correction' has no loss to write off.
        if attrs.get("book_as_expense") and adj_type != "remove":
            raise serializers.ValidationError(
                {"book_as_expense": "Only a 'remove' adjustment can be booked as a loss expense."}
            )
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        product = validated_data["product"]
        quantity = validated_data["quantity"]
        book_as_expense = validated_data.pop("book_as_expense", False)
        expense_amount = validated_data.pop("expense_amount", None)

        with transaction.atomic():
            locked_product = Product.objects.select_for_update().get(pk=product.pk)
            stock_before = locked_product.stock_level
            stock_after = stock_before + quantity

            adjustment = StockAdjustment.objects.create(
                branch_id=request.branch_id,
                product=locked_product,
                adjustment_type=validated_data["adjustment_type"],
                quantity=quantity,
                reason=validated_data["reason"],
                adjusted_by=request.user,
                stock_before=stock_before,
                stock_after=stock_after,
            )
            # A stock adjustment deliberately does NOT touch average_cost
            # (Phase 2 design §7A.5): removing units doesn't change what
            # the rest cost, and an "add"/"correction" carries no cost, so
            # the added units simply inherit the current average. Only a
            # purchase (and void restoration) moves the cost basis.
            locked_product.stock_level = stock_after
            locked_product.save(update_fields=["stock_level", "updated_at", "version"])

            write_outbox_entry(instance=adjustment, operation=OutboxEntry.INSERT, branch_id=request.branch_id)

            booked = None
            if book_as_expense:
                # Lazy import: finances depends on inventory (the FK), so
                # importing it at module scope would form a cycle.
                booked = self._book_loss_expense(request, locked_product, quantity, expense_amount, adjustment)

            self._log_adjustment(request, locked_product, adjustment, booked)

        return adjustment

    @staticmethod
    def _log_adjustment(request, product, adjustment, booked_entry):
        from apps.activity.services import log_activity

        action = adjustment.adjustment_type  # add | remove | correction
        summary = f"Stock {action}: {product.name} {adjustment.quantity:+d} ({adjustment.reason})"
        log_activity(
            request,
            action="stock.adjust",
            summary=summary,
            target=adjustment,
            metadata={"quantity": adjustment.quantity, "type": action},
        )
        if booked_entry is not None:
            log_activity(
                request,
                action="stock.loss_booked",
                summary=f"Booked {booked_entry.amount:,} XAF loss for {product.name}",
                target=booked_entry,
                metadata={"amount": booked_entry.amount},
            )

    @staticmethod
    def _book_loss_expense(request, product, quantity, expense_amount, adjustment):
        """Create the Losses/Damage cashbook expense for a confirmed
        damage/expiry removal (step 8d). Amount defaults to the value lost
        at cost (|qty| × average_cost); a product with no cost basis has
        nothing to write off, so no entry is created."""
        from apps.finances.models import CashbookEntry, ExpenseCategory

        if expense_amount is None:
            expense_amount = abs(quantity) * (product.average_cost or 0)
        if not expense_amount:
            return None  # cost-unknown or zero — nothing to book

        # Default manager already excludes soft-deleted rows, so this
        # reuses an existing Losses/Damage category or seeds it on demand.
        category, _ = ExpenseCategory.objects.get_or_create(
            branch_id=request.branch_id,
            name="Losses/Damage",
        )
        entry = CashbookEntry.objects.create(
            branch_id=request.branch_id,
            direction=CashbookEntry.EXPENSE,
            category=category,
            amount=expense_amount,
            occurred_on=timezone.localdate(),
            description=f"Damage/expiry: {product.name} ×{abs(quantity)}",
            recorded_by=request.user,
            source_adjustment=adjustment,
        )
        write_outbox_entry(instance=entry, operation=OutboxEntry.INSERT, branch_id=request.branch_id)
        return entry


class ProductTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductTemplate
        fields = ["id", "key", "name", "description", "icon"]
