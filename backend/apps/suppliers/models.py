"""
Suppliers & Purchases (design doc Part D / API E.4).

Recording a Purchase is the "one-action restock" (design doc B.4): the
transaction that creates the Purchase + its PurchaseLineItems is the
same transaction that increments each line's Product.stock_level — no
separate inventory-adjustment step needed, mirroring the
select_for_update() pattern already used by
inventory.StockAdjustmentSerializer and sales.SaleSerializer.
"""
from django.conf import settings
from django.db import models

from apps.core.models import BaseModel
from apps.inventory.models import Product


class Supplier(BaseModel):
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True, default="")
    area = models.CharField(max_length=150, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta(BaseModel.Meta):
        ordering = ["name"]

    def __str__(self):
        return self.name


class Purchase(BaseModel):
    PAID = "paid"
    PARTIAL = "partial"
    CREDIT = "credit"
    PAYMENT_STATUS_CHOICES = [
        (PAID, "Paid"),
        (PARTIAL, "Partial"),
        (CREDIT, "Credit"),
    ]

    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchases")
    purchase_date = models.DateField()
    # total_amount is always the sum of its line items' line_total,
    # computed server-side in PurchaseSerializer.create() — never
    # client-supplied, same principle as Sale.subtotal/total_amount.
    total_amount = models.PositiveIntegerField()
    amount_paid = models.PositiveIntegerField(default=0)
    # Derived from amount_paid vs total_amount at creation time (see
    # PurchaseSerializer.create()), not client-supplied either — keeps
    # the two numbers from ever disagreeing with the label.
    payment_status = models.CharField(max_length=10, choices=PAYMENT_STATUS_CHOICES)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="purchases_recorded",
    )

    class Meta(BaseModel.Meta):
        ordering = ["-purchase_date", "-created_at"]

    def __str__(self):
        return f"Purchase from {self.supplier.name} on {self.purchase_date}"


class PurchaseLineItem(BaseModel):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name="line_items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="purchase_line_items")
    quantity = models.PositiveIntegerField()
    unit_cost = models.PositiveIntegerField()
    line_total = models.PositiveIntegerField()

    class Meta(BaseModel.Meta):
        pass

    def __str__(self):
        return f"{self.product.name} x{self.quantity} @ {self.unit_cost}"
