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
from apps.inventory.services import resolve_price_bounds  # re-exported for callers  # noqa: F401


def price_needs_approval(catalogue_price: int, actual_price: int, floor_pct: int, ceiling_pct: int) -> bool:
    """
    True when `actual_price` falls outside the allowed band around
    `catalogue_price` (§3.2), i.e. a discount deeper than floor_pct or a
    surplus higher than ceiling_pct — the cases that need a manager PIN.

    Uses integer XAF thresholds (round the percentage of catalogue). At
    catalogue price exactly, or anywhere inside the band, no approval.
    """
    if actual_price < catalogue_price:
        # Discount: how far below catalogue is allowed.
        min_allowed = catalogue_price - (catalogue_price * floor_pct) // 100
        return actual_price < min_allowed
    if actual_price > catalogue_price:
        # Surplus: how far above catalogue is allowed.
        max_allowed = catalogue_price + (catalogue_price * ceiling_pct) // 100
        return actual_price > max_allowed
    return False


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
