"""
Customer credit balance and debt aging (Phase 2 design §4.3, §4.5).

Balance is always derived here, never read from a stored column — see
models.py for why.
"""
from django.db.models import Sum
from django.utils import timezone


def _credit_sales_qs(customer):
    # Imported lazily: sales imports nothing from customers, and importing
    # Sale at module load would risk an app-loading order issue.
    from apps.sales.models import Sale

    return Sale.objects.filter(
        customer=customer,
        payment_method=Sale.CREDIT,
        status=Sale.COMPLETED,
    )


def total_credit_billed(customer):
    return _credit_sales_qs(customer).aggregate(s=Sum("total_amount"))["s"] or 0


def total_paid(customer):
    return customer.payments.aggregate(s=Sum("amount"))["s"] or 0


def customer_balance(customer):
    """
    What the customer currently owes:
        Σ(completed credit sale totals) − Σ(payments received).

    Voided credit sales are excluded (status filter) — they never
    happened. Negative is possible if a customer overpaid; callers that
    care (credit-limit checks) clamp at zero.
    """
    return total_credit_billed(customer) - total_paid(customer)


def aging_buckets(customer, as_of=None):
    """
    Splits the customer's outstanding balance into age buckets
    (§4.5 aged-debt report): 0–30, 31–60, 61+ days.

    Payments are applied FIFO — oldest credit sale first — so the debt
    that remains unpaid is aged by the date of the sales that are still
    outstanding, which is how a real ledger ages. Returns whole XAF per
    bucket plus the total.
    """
    as_of = as_of or timezone.localdate()
    sales = list(
        _credit_sales_qs(customer).order_by("created_at").values("created_at", "total_amount")
    )
    remaining_payment = total_paid(customer)

    buckets = {"bucket_0_30": 0, "bucket_31_60": 0, "bucket_61_plus": 0}
    for sale in sales:
        amount = sale["total_amount"]
        applied = min(remaining_payment, amount)
        remaining_payment -= applied
        unpaid = amount - applied
        if unpaid <= 0:
            continue
        sale_date = timezone.localtime(sale["created_at"]).date()
        age_days = (as_of - sale_date).days
        if age_days <= 30:
            buckets["bucket_0_30"] += unpaid
        elif age_days <= 60:
            buckets["bucket_31_60"] += unpaid
        else:
            buckets["bucket_61_plus"] += unpaid

    buckets["total"] = sum(buckets.values())
    return buckets
