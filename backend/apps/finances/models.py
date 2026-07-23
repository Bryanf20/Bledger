"""
Finances & cashbook (Phase 2 design §7B.2).

The expense side of the ledger. Cost tracking (workstream G) gives gross
margin (revenue − cost of goods); this gives the operating expenses —
rent, transport, salaries, utilities, stock written off — that turn
gross margin into the *net* profit an owner actually keeps.

Deliberately a lightweight single-entry cashbook (money out = expense,
the rare money in = non-sale income), NOT double-entry accounting —
OHADA statements remain Phase 4. This is the raw material OHADA will
later formalise, a stepping stone rather than a duplicate.

Editability differs from sales/purchases ON PURPOSE (§7B.2): a sale is a
customer-facing transaction and is immutable (corrections go through
void). An expense is the owner's own bookkeeping, where a mistyped
amount is common and harmless to fix — so CashbookEntry is editable and
soft-deletable by the owner, a considered exception to the
"financial records are immutable" convention.

Branch-scoped (each branch has its own rent and transport), so it syncs
branch → cloud like sales.
"""
from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class ExpenseCategory(BaseModel):
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)

    class Meta(BaseModel.Meta):
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["branch_id", "name"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_expense_category_per_branch",
            )
        ]

    def __str__(self):
        return self.name


class CashbookEntry(BaseModel):
    EXPENSE = "expense"
    INCOME = "income"
    DIRECTION_CHOICES = [
        (EXPENSE, "Expense (money out)"),
        (INCOME, "Income (money in)"),
    ]

    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES, default=EXPENSE)
    # Categorises an expense; income is rare and left uncategorised.
    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="entries",
    )
    amount = models.PositiveIntegerField()
    occurred_on = models.DateField()
    description = models.CharField(max_length=255, blank=True, default="")
    payment_method = models.CharField(max_length=20, blank=True, default="cash")
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="cashbook_entries",
    )

    class Meta(BaseModel.Meta):
        ordering = ["-occurred_on", "-created_at"]

    def __str__(self):
        return f"{self.direction} {self.amount} XAF on {self.occurred_on}"
