"""
Brokered / commission sales (Phase 2 design §7B.1): the shop sells an
item it doesn't stock, sourcing it externally at delivery time. Such a
line moves no stock, records the external cost as its COGS, and its gain
(price - external cost) still flows into margin. Voiding it must not
invent phantom stock.
"""
import pytest

from apps.inventory.models import Product
from apps.sales.models import SaleLineItem

from .conftest import BRANCH_ID, api_client_for

pytestmark = pytest.mark.django_db


@pytest.fixture
def out_of_stock_product(category):
    # A catalogued product the shop is currently out of — the common
    # brokered case. Retail 10,000; no stock.
    return Product.objects.create(
        branch_id=BRANCH_ID, name="Gas cylinder", category=category,
        retail_price=10000, stock_level=0,
    )


def _sell(client, items):
    return client.post(
        "/api/v1/sales/", {"payment_method": "cash", "items": items}, format="json"
    )


def test_brokered_line_sells_with_no_stock(owner_user, out_of_stock_product):
    client = api_client_for(owner_user)
    resp = _sell(client, [{
        "product": str(out_of_stock_product.id), "quantity": 1,
        "is_brokered": True, "external_cost": 8000, "source_note": "Neighbour Eric",
    }])
    assert resp.status_code == 201, resp.data

    line = SaleLineItem.objects.get(sale_id=resp.data["id"])
    assert line.is_brokered is True
    assert line.unit_cost_at_sale == 8000        # external cost as COGS
    assert line.source_note == "Neighbour Eric"
    assert line.catalogue_price == 10000         # sold at catalogue price
    # Gain = 10000 - 8000 = 2000 (surfaced via margin reporting later).


def test_brokered_line_does_not_move_stock(owner_user, out_of_stock_product):
    client = api_client_for(owner_user)
    _sell(client, [{
        "product": str(out_of_stock_product.id), "quantity": 2,
        "is_brokered": True, "external_cost": 8000,
    }])
    out_of_stock_product.refresh_from_db()
    assert out_of_stock_product.stock_level == 0  # never touched


def test_brokered_requires_external_cost(owner_user, out_of_stock_product):
    client = api_client_for(owner_user)
    resp = _sell(client, [{
        "product": str(out_of_stock_product.id), "quantity": 1, "is_brokered": True,
    }])
    assert resp.status_code == 400
    assert "external_cost" in str(resp.data)


def test_normal_line_still_needs_stock(owner_user, out_of_stock_product):
    """Without the brokered flag, an out-of-stock product is still refused."""
    client = api_client_for(owner_user)
    resp = _sell(client, [{"product": str(out_of_stock_product.id), "quantity": 1}])
    assert resp.status_code == 400
    assert "Insufficient stock" in str(resp.data)


def test_mixed_cart_normal_and_brokered(owner_user, category, out_of_stock_product):
    """A normal in-stock line and a brokered line in one sale."""
    client = api_client_for(owner_user)
    stocked = Product.objects.create(
        branch_id=BRANCH_ID, name="Matches", category=category,
        retail_price=100, stock_level=50, average_cost=60, cost_is_set=True,
    )
    resp = _sell(client, [
        {"product": str(stocked.id), "quantity": 5},
        {"product": str(out_of_stock_product.id), "quantity": 1,
         "is_brokered": True, "external_cost": 8000},
    ])
    assert resp.status_code == 201, resp.data

    stocked.refresh_from_db()
    out_of_stock_product.refresh_from_db()
    assert stocked.stock_level == 45              # decremented
    assert out_of_stock_product.stock_level == 0  # untouched

    lines = {l.product_id: l for l in SaleLineItem.objects.filter(sale_id=resp.data["id"])}
    assert lines[stocked.id].is_brokered is False
    assert lines[stocked.id].unit_cost_at_sale == 60      # product average cost
    assert lines[out_of_stock_product.id].is_brokered is True
    assert lines[out_of_stock_product.id].unit_cost_at_sale == 8000  # external


def test_voiding_brokered_sale_does_not_restore_stock(owner_user, out_of_stock_product):
    """
    A brokered line never moved stock, so voiding must not add phantom
    stock or touch the cost basis.
    """
    client = api_client_for(owner_user)
    sale = _sell(client, [{
        "product": str(out_of_stock_product.id), "quantity": 3,
        "is_brokered": True, "external_cost": 8000,
    }])
    r = client.post(
        f"/api/v1/sales/{sale.data['id']}/void/", {"void_reason": "customer cancelled"},
        format="json",
    )
    assert r.status_code == 200
    out_of_stock_product.refresh_from_db()
    assert out_of_stock_product.stock_level == 0     # NOT +3
    assert out_of_stock_product.average_cost == 0    # untouched


def test_voiding_mixed_sale_restores_only_the_normal_line(owner_user, category, out_of_stock_product):
    client = api_client_for(owner_user)
    stocked = Product.objects.create(
        branch_id=BRANCH_ID, name="Matches", category=category,
        retail_price=100, stock_level=50, average_cost=60, cost_is_set=True,
    )
    sale = _sell(client, [
        {"product": str(stocked.id), "quantity": 5},
        {"product": str(out_of_stock_product.id), "quantity": 1,
         "is_brokered": True, "external_cost": 8000},
    ])
    stocked.refresh_from_db()
    assert stocked.stock_level == 45

    client.post(f"/api/v1/sales/{sale.data['id']}/void/", {"void_reason": "x"}, format="json")

    stocked.refresh_from_db()
    out_of_stock_product.refresh_from_db()
    assert stocked.stock_level == 50              # restored
    assert out_of_stock_product.stock_level == 0  # brokered — untouched
