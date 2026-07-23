"""
Cost tracking on the purchase side (Phase 2 design §7A): a purchase
establishes or moves the weighted-average cost, records last_cost, flags
cost_is_set, and snapshots the product name onto the line.
"""
import pytest

from apps.inventory.models import Category, Product
from apps.suppliers.models import PurchaseLineItem, Supplier

BRANCH_ID = "HQ"

pytestmark = pytest.mark.django_db


@pytest.fixture
def supplier(db):
    return Supplier.objects.create(branch_id=BRANCH_ID, name="Bafang Distributors")


@pytest.fixture
def fresh_product(category):
    # Zero stock, no cost basis — the clean starting point for WAC math.
    return Product.objects.create(
        branch_id=BRANCH_ID, name="Rice 5kg", category=category,
        retail_price=4500, stock_level=0,
    )


def _purchase(client, supplier, product, qty, unit_cost):
    r = client.post(
        "/api/v1/purchases/",
        {
            "supplier": str(supplier.id),
            "purchase_date": "2026-06-01",
            "amount_paid": 0,
            "items": [{"product": str(product.id), "quantity": qty, "unit_cost": unit_cost}],
        },
        format="json",
    )
    assert r.status_code == 201, r.data
    return r


def test_first_purchase_establishes_cost(owner_client, supplier, fresh_product):
    _purchase(owner_client, supplier, fresh_product, 20, 3000)
    fresh_product.refresh_from_db()
    assert fresh_product.average_cost == 3000
    assert fresh_product.last_cost == 3000
    assert fresh_product.cost_is_set is True


def test_second_purchase_blends_to_weighted_average(owner_client, supplier, fresh_product):
    _purchase(owner_client, supplier, fresh_product, 20, 3000)   # avg 3000
    _purchase(owner_client, supplier, fresh_product, 30, 3500)   # (20*3000+30*3500)/50
    fresh_product.refresh_from_db()
    assert fresh_product.average_cost == 3300
    assert fresh_product.last_cost == 3500  # most recent


def test_first_purchase_ignores_phantom_zero_cost_opening_stock(owner_client, supplier, category):
    """
    A product with existing stock but no cost basis: the first purchase
    ESTABLISHES the cost (incoming unit_cost) rather than blending it
    against the phantom average_cost=0 of the opening units.
    """
    p = Product.objects.create(
        branch_id=BRANCH_ID, name="Opening 50", category=category,
        retail_price=4000, stock_level=50,  # cost unknown
    )
    _purchase(owner_client, supplier, p, 50, 3800)
    p.refresh_from_db()
    # Establishes at 3800, NOT (50*0 + 50*3800)/100 = 1900.
    assert p.average_cost == 3800
    assert p.stock_level == 100


def test_purchase_line_snapshots_product_name(owner_client, supplier, fresh_product):
    r = _purchase(owner_client, supplier, fresh_product, 10, 3000)
    line = PurchaseLineItem.objects.get(purchase_id=r.data["id"])
    assert line.product_name == "Rice 5kg"
