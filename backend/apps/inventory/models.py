"""
Inventory app — Category, Product, BranchPriceOverride, StockAdjustment,
ProductTemplate.

Per design doc Part D / C.2 and Feasibility doc Section 9.2 / 9.3:

    Category               name, description, sort_order. Branch-owned —
                            each branch can customise categories.
    Product                name, category FK, unit, retail_price,
                            bulk_price, bulk_min_qty, stock_level,
                            low_stock_threshold, is_active, source
                            (template/manual). HQ catalogue products use
                            branch_id=HQ_BRANCH_ID.
    BranchPriceOverride     product FK, retail/bulk price + bulk_min_qty
                            overrides, set_by FK (owner/manager only).
                            Unique per (product, branch).
    StockAdjustment        product FK, adjustment_type (add/remove/
                            correction), quantity (signed), reason
                            (required), adjusted_by FK, stock_before/
                            stock_after snapshots. Never deleted — full
                            audit trail.
    ProductTemplate        NOT a BaseModel — a small, fixed, global
                            catalogue of starter templates (Provision
                            Store, Boutique, Cosmetics, Electronics),
                            identical across every install. Seed rows are
                            created by migrations/0002_seed_product_templates.py.
                            The actual products/categories each template
                            loads live in fixtures/<fixture_name>.json and
                            are applied by services.load_template().
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import BaseModel

# HQ catalogue products/categories live at this branch_id. In Phase 1
# standalone (single branch per install) this distinction is mostly
# latent — every product is created directly on the one real branch —
# but it's the seam Phase 2 multi-branch sync relies on (Feasibility doc
# Section 6: catalogue is HQ-owned, pushed to branches read-only).
HQ_BRANCH_ID = "HQ"

PRODUCT_SOURCE_CHOICES = [
    ("template", "Template"),
    ("manual", "Manual"),
]

ADJUSTMENT_TYPE_CHOICES = [
    ("add", "Add (restock)"),
    ("remove", "Remove (damage/expiry)"),
    ("correction", "Correction (count discrepancy)"),
]


class Category(BaseModel):
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=255, blank=True, default="")
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["branch_id", "name"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_category_name_per_branch",
            )
        ]

    def __str__(self):
        return self.name


class Product(BaseModel):
    name = models.CharField(max_length=150)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    unit = models.CharField(max_length=30, default="unit")

    retail_price = models.PositiveIntegerField(validators=[MinValueValidator(0)])
    bulk_price = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(0)])
    bulk_min_qty = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(2)])

    # Never edited directly by the API — only StockAdjustment.create()
    # (and, once built, the suppliers app recording a purchase) is
    # allowed to move this number, and both do so atomically.
    stock_level = models.IntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=5)

    # Deactivation, not deletion (design doc B.3) — preserves sale
    # history. Deactivated products drop out of the POS grid but stay
    # on past receipts/reports.
    is_active = models.BooleanField(default=True)
    source = models.CharField(max_length=10, choices=PRODUCT_SOURCE_CHOICES, default="manual")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
        if bool(self.bulk_price) != bool(self.bulk_min_qty):
            raise ValidationError("bulk_price and bulk_min_qty must be set together.")

    @property
    def stock_status(self):
        if self.stock_level <= 0:
            return "out"
        if self.stock_level <= self.low_stock_threshold:
            return "low"
        return "ok"


class BranchPriceOverride(BaseModel):
    """
    Only meaningful once Phase 2 multi-branch is live. In Phase 1
    standalone (single branch) this table exists per the schema but is
    rarely populated — see Feasibility doc Section 9.3: "Only the owner
    or manager role may set branch price overrides."
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="price_overrides")
    retail_price_override = models.PositiveIntegerField(null=True, blank=True)
    bulk_price_override = models.PositiveIntegerField(null=True, blank=True)
    bulk_min_qty_override = models.PositiveIntegerField(null=True, blank=True)
    set_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="price_overrides_set",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["product", "branch_id"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_override_per_product_branch",
            )
        ]

    def __str__(self):
        return f"{self.product.name} override @ {self.branch_id}"


class StockAdjustment(BaseModel):
    """
    Full audit trail. Rows are created once and never updated or
    deleted — stock_before/stock_after are point-in-time snapshots taken
    atomically with the Product.stock_level write (see
    serializers.StockAdjustmentSerializer.create()).
    """
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="adjustments")
    adjustment_type = models.CharField(max_length=12, choices=ADJUSTMENT_TYPE_CHOICES)
    quantity = models.IntegerField(help_text="Signed — positive for add, negative for remove.")
    reason = models.CharField(max_length=255)
    adjusted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="stock_adjustments",
    )
    stock_before = models.IntegerField()
    stock_after = models.IntegerField()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.product.name}: {self.quantity:+d} ({self.adjustment_type})"


class ProductTemplate(models.Model):
    """
    Global, not branch-scoped — the same four templates exist on every
    install (design doc B.7 / API E.6). Deliberately NOT a BaseModel:
    there's nothing here to sync, soft-delete, or version.
    """
    key = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=255, blank=True, default="")
    icon = models.CharField(max_length=10, blank=True, default="")
    fixture_name = models.CharField(max_length=80, help_text="Filename under apps/inventory/fixtures/")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
