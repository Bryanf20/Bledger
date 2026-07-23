"""
Cost tracking on the sales side (Phase 2 design §7A): COGS snapshot at
sale time, the rule that selling doesn't move the average, and the
drift-safe void — the subtle correctness point where a void after an
intervening purchase must restore cost "as if the sale never happened".
"""
import pytest

from apps.inventory.models import Category, Product
from apps.sales.models import Sale, SaleLineItem

from .conftest import BRANCH_ID, api_client_for

pytestmark = pytest.mark.django_db


@pytest.fixture
def supplier(db):
    from apps.suppliers.models import Supplier
    return Supplier.objects.create(branch_id=BRANCH_ID, name="Bafang Distributors")


@pytest.fixture
def zero_stock_product(category):
    return Product.objects.create(
        branch_id=BRANCH_ID, name="Rice", category=category,
        retail_price=4000, stock_level=0,
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


def _sell(client, product, qty):
    r = client.post(
        "/api/v1/sales/",
        {"payment_method": "cash", "items": [{"product": str(product.id), "quantity": qty}]},
        format="json",
    )
    assert r.status_code == 201, r.data
    return r


def test_sale_snapshots_cogs_and_name(owner_user, supplier, zero_stock_product):
    client = api_client_for(owner_user)
    _purchase(client, supplier, zero_stock_product, 20, 3000)  # avg -> 3000

    sale = _sell(client, zero_stock_product, 5)
    line = SaleLineItem.objects.get(sale_id=sale.data["id"])
    assert line.unit_cost_at_sale == 3000       # COGS snapshot
    assert line.product_name == "Rice"          # name snapshot


def test_selling_does_not_change_average_cost(owner_user, supplier, zero_stock_product):
    client = api_client_for(owner_user)
    _purchase(client, supplier, zero_stock_product, 20, 3000)
    _sell(client, zero_stock_product, 5)

    zero_stock_product.refresh_from_db()
    assert zero_stock_product.average_cost == 3000  # unchanged by the sale
    assert zero_stock_product.stock_level == 15


def test_void_after_purchase_restores_cost_as_if_never_sold(owner_user, supplier, zero_stock_product):
    """
    The drift-safety property (§7A.5). Sell before an intervening
    purchase moves the average; voiding must return the average to what
    it would be had the sale never happened — not to the current (moved)
    average, which would drift on every void/resell cycle.
    """
    client = api_client_for(owner_user)

    _purchase(client, supplier, zero_stock_product, 20, 3000)   # 20 @ 3000, avg 3000
    sale = _sell(client, zero_stock_product, 5)                 # snapshot COGS 3000, stock 15
    _purchase(client, supplier, zero_stock_product, 30, 3500)   # avg -> 3333, stock 45

    zero_stock_product.refresh_from_db()
    assert zero_stock_product.average_cost == 3333  # (15*3000 + 30*3500)/45

    # Void the original sale of 5.
    r = client.post(
        f"/api/v1/sales/{sale.data['id']}/void/", {"void_reason": "customer returned"}, format="json"
    )
    assert r.status_code == 200

    zero_stock_product.refresh_from_db()
    # As if never sold: 20 @ 3000 then 30 @ 3500 = 50 units / 165000 = 3300.
    assert zero_stock_product.average_cost == 3300
    assert zero_stock_product.stock_level == 50


def test_void_of_costless_sale_leaves_average_untouched(owner_user, category):
    """
    A sale of a product with no cost basis snapshots unit_cost_at_sale=0;
    voiding it must NOT blend that 0 into the average — it just restores
    stock.
    """
    client = api_client_for(owner_user)
    p = Product.objects.create(
        branch_id=BRANCH_ID, name="No cost", category=category,
        retail_price=1000, stock_level=10,  # cost_is_set defaults False, avg 0
    )
    sale = _sell(client, p, 3)
    line = SaleLineItem.objects.get(sale_id=sale.data["id"])
    assert line.unit_cost_at_sale == 0

    client.post(f"/api/v1/sales/{sale.data['id']}/void/", {"void_reason": "x"}, format="json")
    p.refresh_from_db()
    assert p.average_cost == 0
    assert p.stock_level == 10


def test_receipt_uses_snapshotted_name(owner_user, supplier, zero_stock_product):
    from apps.sales.receipt_data import build_receipt_context

    client = api_client_for(owner_user)
    _purchase(client, supplier, zero_stock_product, 10, 3000)
    sale = _sell(client, zero_stock_product, 2)

    # Rename the product AFTER the sale — the receipt must still show the
    # name as it was when sold.
    zero_stock_product.name = "Rice (new packaging)"
    zero_stock_product.save(update_fields=["name"])

    sale_obj = Sale.objects.get(pk=sale.data["id"])
    context = build_receipt_context(sale_obj)
    assert context["line_items"][0]["name"] == "Rice"
