"""
Inventory serializers.

Product.stock_level only ever moves through StockAdjustmentSerializer.create()
here (and, once built, the suppliers app recording a purchase) — both do
so atomically inside a transaction so stock_before/stock_after snapshots
stay trustworthy for the audit trail.
"""
from django.db import transaction
from rest_framework import serializers

from .models import (
    BranchPriceOverride,
    Category,
    Product,
    ProductTemplate,
    StockAdjustment,
)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "description", "sort_order", "created_at", "updated_at"]
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

    class Meta:
        model = Product
        fields = [
            "id", "name", "category", "category_name", "unit",
            "retail_price", "bulk_price", "bulk_min_qty",
            "stock_level", "low_stock_threshold", "stock_status",
            "is_active", "source",
            "effective_retail_price", "effective_bulk_price",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "stock_level", "source", "created_at", "updated_at"]

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

        override, _created = BranchPriceOverride.objects.update_or_create(
            product=product,
            branch_id=request.branch_id,
            defaults={
                "retail_price_override": validated_data.get("retail_price_override"),
                "bulk_price_override": validated_data.get("bulk_price_override"),
                "bulk_min_qty_override": validated_data.get("bulk_min_qty_override"),
                "set_by": request.user,
            },
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

    class Meta:
        model = StockAdjustment
        fields = [
            "id", "product", "product_name", "adjustment_type", "quantity",
            "reason", "adjusted_by", "stock_before", "stock_after", "created_at",
        ]
        read_only_fields = ["id", "adjusted_by", "stock_before", "stock_after", "created_at"]

    def validate(self, attrs):
        adj_type = attrs["adjustment_type"]
        quantity = attrs["quantity"]
        if adj_type == "add" and quantity <= 0:
            raise serializers.ValidationError("Quantity must be positive for an 'add' adjustment.")
        if adj_type == "remove" and quantity >= 0:
            raise serializers.ValidationError("Quantity must be negative for a 'remove' adjustment.")
        if not attrs.get("reason", "").strip():
            raise serializers.ValidationError("A reason is required for every stock adjustment.")
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        product = validated_data["product"]
        quantity = validated_data["quantity"]

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
            locked_product.stock_level = stock_after
            locked_product.save(update_fields=["stock_level", "updated_at", "version"])

        return adjustment


class ProductTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductTemplate
        fields = ["id", "key", "name", "description", "icon"]
