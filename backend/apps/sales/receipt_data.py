"""
Builds the plain-dict `sale_data` apps.printing.interface.print_receipt()
expects (design doc 8.4) from a real Sale instance. Lives here, not in
apps.printing, so the printing app never has to import apps.sales — it
stays a pure rendering layer that only ever sees dicts (see
apps.printing.interface's module docstring).
"""
from django.utils import timezone

from apps.core.utils.xaf import format_xaf


def build_receipt_context(sale):
    branch = sale.cashier.branch
    created_local = timezone.localtime(sale.created_at)

    line_items = [
        {
            # Snapshotted name (§7A.1) so a later product rename doesn't
            # rewrite this receipt; fall back for pre-snapshot rows.
            "name": item.product_name or item.product.name,
            "quantity": item.quantity,
            "line_total": format_xaf(item.line_total),
        }
        for item in sale.line_items.select_related("product").all()
    ]

    # On a credit sale, show who owes and their balance after this sale
    # (Phase 2 §4.5) so the customer has a record of the debt.
    customer_name = None
    customer_balance_str = None
    if sale.customer_id is not None:
        from apps.customers.services import customer_balance

        customer_name = sale.customer.name
        if sale.payment_method == sale.CREDIT:
            customer_balance_str = format_xaf(customer_balance(sale.customer))

    return {
        "business_name": branch.business_name,
        "customer_name": customer_name,
        "customer_balance": customer_balance_str,
        "branch_name": branch.branch_name,
        "address": branch.address,
        "phone": branch.phone,
        "receipt_footer": branch.receipt_footer,
        "date": created_local.strftime("%d/%m/%Y"),
        "time": created_local.strftime("%H:%M"),
        "cashier_name": sale.cashier.name,
        # "Sale #0047" on the receipt (design doc B.2 / 02_receipt.html)
        # is the sequence tail of the BLD-<branch_code>-YYYY-NNNN
        # reference, not the reference itself. Taking the last
        # hyphen-separated segment keeps this correct across the Phase 2
        # §8.1 format change — the sequence has always been last.
        "sale_number": sale.reference.rsplit("-", 1)[-1],
        "reference": sale.reference,
        "line_items": line_items,
        "subtotal": format_xaf(sale.subtotal),
        "tax_rate": "0%",  # no tax in Phase 1 (see sales.serializers.SaleSerializer)
        "tax_amount": format_xaf(sale.tax_amount),
        "total_amount": format_xaf(sale.total_amount),
        "payment_method": sale.get_payment_method_display(),
        "momo_reference": sale.momo_reference,
    }
