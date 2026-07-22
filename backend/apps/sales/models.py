from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class Sale(BaseModel):
    CASH = "cash"
    MTN_MOMO = "mtn_momo"
    ORANGE_MONEY = "orange_money"
    OTHER = "other"
    PAYMENT_METHOD_CHOICES = [
        (CASH, "Cash"),
        (MTN_MOMO, "MTN MoMo"),
        (ORANGE_MONEY, "Orange Money"),
        (OTHER, "Other"),
    ]

    COMPLETED = "completed"
    VOIDED = "voided"
    STATUS_CHOICES = [
        (COMPLETED, "Completed"),
        (VOIDED, "Voided"),
    ]

    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sales"
    )
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)

    # Required together when payment_method is MTN/Orange (Feasibility
    # doc Section 9.5). Blank/False for cash/other.
    momo_reference = models.CharField(max_length=64, blank=True, default="")
    momo_confirmed = models.BooleanField(default=False)

    subtotal = models.PositiveIntegerField()
    tax_amount = models.PositiveIntegerField(default=0)
    total_amount = models.PositiveIntegerField()
    amount_tendered = models.PositiveIntegerField(null=True, blank=True)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=COMPLETED)

    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="voided_sales",
        null=True,
        blank=True,
    )
    void_reason = models.TextField(null=True, blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)

    # Human-facing sale ref for the receipt/dashboard (design doc B.2):
    # BLD-<branch_code>-YYYY-NNNN. Not the pk — a separate
    # per-branch-per-year sequence. The branch code is what keeps
    # references unique once several branches share a cloud database
    # (Phase 2 design §8.1); without it every branch would generate
    # BLD-2026-0001 independently.
    reference = models.CharField(max_length=20, unique=True, editable=False)

    class Meta(BaseModel.Meta):
        pass

    def __str__(self):
        return self.reference or str(self.id)


class SaleLineItem(BaseModel):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="line_items")
    product = models.ForeignKey(
        "inventory.Product", on_delete=models.PROTECT, related_name="sale_line_items"
    )
    quantity = models.PositiveIntegerField()

    # Phase 2 haggling fields — catalogue_price == actual_price,
    # variance == 0, variance_approved_by == None in Phase 1
    # (Feasibility doc Section 9.4). Live from day one so Phase 2
    # (negotiated pricing) needs no migration.
    catalogue_price = models.PositiveIntegerField()
    actual_price = models.PositiveIntegerField()
    variance = models.IntegerField(default=0)
    variance_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="approved_variances",
        null=True,
        blank=True,
    )

    line_total = models.PositiveIntegerField()

    class Meta(BaseModel.Meta):
        pass


class HeldSale(BaseModel):
    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="held_sales"
    )
    label = models.CharField(max_length=100, blank=True, default="")
    cart_data = models.JSONField()

    class Meta(BaseModel.Meta):
        pass

    @property
    def held_at(self):
        # Design doc lists held_at as its own field; BaseModel already
        # gives us created_at, so this is an alias rather than a second
        # timestamp column.
        return self.created_at
