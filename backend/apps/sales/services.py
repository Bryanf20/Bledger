"""
Price resolution for the POS.

ASSUMPTION FLAGGED: this reads BranchPriceOverride directly rather than
reusing apps.inventory.serializers.ProductSerializer's effective-price
logic, because that logic is exposed as computed *output* fields, not a
plain function. Verify this resolves prices identically to what the POS
product grid displays (apps.inventory) before relying on it in
production — if the actual resolution differs (e.g. how
bulk_min_qty_override interacts with retail vs bulk selection), fix
here, not there.
"""
from apps.inventory.models import BranchPriceOverride, Product


def resolve_unit_price(product: Product, branch_id: str, quantity: int) -> int:
    """
    Price per unit this branch charges for `quantity` units of
    `product` right now: bulk price if quantity meets the (possibly
    overridden) bulk threshold, else retail price — each itself
    possibly overridden for this branch.
    """
    override = (
        BranchPriceOverride.objects.filter(product=product, branch_id=branch_id)
        .order_by("-created_at")
        .first()
    )

    retail_price = product.retail_price
    bulk_price = product.bulk_price
    bulk_min_qty = product.bulk_min_qty

    if override:
        if override.retail_price_override is not None:
            retail_price = override.retail_price_override
        if override.bulk_price_override is not None:
            bulk_price = override.bulk_price_override
        if override.bulk_min_qty_override is not None:
            bulk_min_qty = override.bulk_min_qty_override

    if bulk_price is not None and bulk_min_qty is not None and quantity >= bulk_min_qty:
        return bulk_price

    return retail_price
