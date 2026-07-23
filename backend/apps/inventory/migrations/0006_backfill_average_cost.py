"""
Backfills Product.average_cost from existing purchase history (Phase 2
design §7A.8).

For every product that has been purchased, average_cost is set to the
weighted-average of its PurchaseLineItems, last_cost to its most recent
purchase, and cost_is_set to True. Products with no purchase history —
template-loaded or manually created before cost tracking — keep
average_cost=0 and cost_is_set=False, so margin reporting excludes them
rather than reporting a misleading 100%% margin. The owner is later
prompted to set those costs (a one-time Inventory task).

Historical SaleLineItem.unit_cost_at_sale cannot be reconstructed and
stays 0, so margin reporting honestly begins from deployment rather than
claiming to cover past sales.

Separate from the 0005 schema migration so it can depend on the
suppliers app (PurchaseLineItem) without the schema change dragging that
dependency in.
"""
from django.db import migrations


def backfill_average_cost(apps, schema_editor):
    Product = apps.get_model("inventory", "Product")
    PurchaseLineItem = apps.get_model("suppliers", "PurchaseLineItem")

    for product in Product.objects.all():
        # all_objects/soft-delete managers aren't carried into historical
        # models, so this is the plain manager — fine, we want every
        # product including soft-deleted ones to carry a sane cost basis.
        lines = list(
            PurchaseLineItem.objects.filter(product_id=product.pk).order_by("created_at")
        )
        if not lines:
            continue  # no basis — leave cost_is_set=False, average_cost=0

        total_qty = sum(li.quantity for li in lines)
        total_value = sum(li.quantity * li.unit_cost for li in lines)
        if total_qty <= 0:
            continue

        # Round half-up to whole XAF without importing app code into the
        # migration (keep it self-contained and frozen).
        average = int((total_value + total_qty // 2) // total_qty)

        product.average_cost = average
        product.last_cost = lines[-1].unit_cost  # most recent purchase
        product.cost_is_set = True
        product.save(update_fields=["average_cost", "last_cost", "cost_is_set"])


def reverse_backfill(apps, schema_editor):
    # Non-reversible in a meaningful sense — we can't know which costs
    # were backfilled vs. later edited. Clear the flag/values back to the
    # field defaults so the reverse at least leaves a consistent state.
    Product = apps.get_model("inventory", "Product")
    Product.objects.update(average_cost=0, last_cost=None, cost_is_set=False)


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0005_product_cost_fields"),
        # Reads PurchaseLineItem — must exist first.
        ("suppliers", "0003_purchaselineitem_product_name"),
    ]

    operations = [
        migrations.RunPython(backfill_average_cost, reverse_backfill),
    ]
