"""
Net-profit computation (Phase 2 design §7B.3).

    net profit = gross margin − operating expenses + non-sale income

Gross margin comes from the same cost-known sale lines the dashboard's
margin summary uses (§7A.6); expenses and income come from the cashbook.
Soft-deleted expenses are excluded automatically (BaseModel's default
manager filters them).
"""
from django.db.models import F, IntegerField, Sum, Value
from django.db.models.functions import Coalesce

from .models import CashbookEntry

_ZERO = Value(0, output_field=IntegerField())


def gross_margin_for_period(branch_id, start, end):
    """(gross_margin, revenue, cogs) over completed, non-voided,
    cost-known sale lines in [start, end)."""
    from apps.sales.models import Sale, SaleLineItem

    sales = Sale.objects.filter(
        branch_id=branch_id, status=Sale.COMPLETED, created_at__gte=start, created_at__lt=end
    )
    costed = SaleLineItem.objects.filter(sale__in=sales, unit_cost_at_sale__gt=0)
    agg = costed.aggregate(
        revenue=Coalesce(Sum("line_total"), _ZERO),
        cogs=Coalesce(Sum(F("unit_cost_at_sale") * F("quantity")), _ZERO),
    )
    return agg["revenue"] - agg["cogs"], agg["revenue"], agg["cogs"]


def period_pnl(branch_id, start, end):
    """Full period profit-and-loss (§7B.3). Expenses/income are matched by
    their `occurred_on` date within the period's date span."""
    gross_margin, revenue, cogs = gross_margin_for_period(branch_id, start, end)

    start_date = start.date()
    end_date = end.date()
    in_period = CashbookEntry.objects.filter(
        branch_id=branch_id, occurred_on__gte=start_date, occurred_on__lte=end_date
    )

    expenses_qs = in_period.filter(direction=CashbookEntry.EXPENSE)
    total_expenses = expenses_qs.aggregate(s=Coalesce(Sum("amount"), _ZERO))["s"]
    total_income = in_period.filter(direction=CashbookEntry.INCOME).aggregate(
        s=Coalesce(Sum("amount"), _ZERO)
    )["s"]

    by_category = [
        {
            "category_id": str(row["category"]) if row["category"] else None,
            "category_name": row["category__name"] or "Uncategorised",
            "total": row["total"],
        }
        for row in (
            expenses_qs.values("category", "category__name")
            .annotate(total=Sum("amount"))
            .order_by("-total")
        )
    ]

    net_profit = gross_margin - total_expenses + total_income
    return {
        "gross_margin": gross_margin,
        "revenue": revenue,
        "cogs": cogs,
        "total_expenses": total_expenses,
        "total_income": total_income,
        "net_profit": net_profit,
        "expenses_by_category": by_category,
    }
