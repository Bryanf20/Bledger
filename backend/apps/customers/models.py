"""
Customers & credit (Phase 2 design §4).

Mirrors the suppliers app in shape — a directory plus an append-only
payment ledger — but points the other way: suppliers are money the shop
*owes*, customers are money *owed to* the shop. Selling on credit
("na go pay you Friday") is ubiquitous in Cameroonian retail and was
previously invisible to Bledger.

Two deliberate design points:

  Branch-scoped (§4.4). A Customer belongs to one branch; credit is
  per-branch. This keeps the sync model intact — no two branches ever
  edit the same customer or balance — the same "branches own their
  records" property that makes multi-branch sync tractable. A person who
  buys on credit at two branches is two Customer rows.

  Balance is DERIVED, never stored (§4.3):
      balance = Σ(credit sale totals) − Σ(customer payments)
  A stored running total on an unbounded, multi-year, cross-transaction
  ledger is the classic drift bug (the stored figure and the ledger
  disagree and nobody knows which is right). Contrast Purchase.amount_paid,
  a stored total that's acceptable because it's scoped to one purchase
  with a bounded payment list. See services.customer_balance().
"""
from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class Customer(BaseModel):
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True, default="")
    area = models.CharField(max_length=150, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)

    # Maximum outstanding credit this customer may carry, in XAF. 0 means
    # no credit is allowed (the default) — a credit sale to them needs
    # manager approval every time. Raising it is a manager/owner action.
    credit_limit = models.PositiveIntegerField(default=0)

    class Meta(BaseModel.Meta):
        ordering = ["name"]

    def __str__(self):
        return self.name


class CustomerPayment(BaseModel):
    """
    One payment received from a customer against their credit balance.
    Append-only — no update or delete route (same permanent-financial-
    record principle as Sale / PurchasePayment). A mistaken entry needs a
    dedicated reversal, not an edit.
    """
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="payments")
    amount = models.PositiveIntegerField()
    payment_date = models.DateField()
    # How the payment came in — mirrors Sale's methods (cash/momo/other).
    payment_method = models.CharField(max_length=20, blank=True, default="cash")
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="customer_payments_recorded",
    )
    note = models.TextField(blank=True, default="")

    class Meta(BaseModel.Meta):
        ordering = ["-payment_date", "-created_at"]

    def __str__(self):
        return f"{self.amount} XAF from {self.customer.name} on {self.payment_date}"
