"""
Cost tracking on the inventory side (Phase 2 design §7A): the
weighted-average helper, price-change history, the rule that stock
adjustments never move cost, and manual cost entry.
"""
import pytest

from apps.inventory.models import Product, ProductPriceHistory
from apps.inventory.services import weighted_average_cost

from .conftest import BRANCH_ID

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# weighted_average_cost helper (pure function)
# ---------------------------------------------------------------------------


def test_wac_blends_two_lots():
    # 20 @ 3000 then +30 @ 3500 -> 50 units, 165000, avg 3300.
    assert weighted_average_cost(20, 3000, 30, 3500) == 3300


def test_wac_zero_stock_takes_incoming_cost():
    # No basis to blend against — the incoming cost is the average.
    assert weighted_average_cost(0, 0, 40, 3300) == 3300


def test_wac_negative_stock_takes_incoming_cost():
    # Oversold, then restocked.
    assert weighted_average_cost(-5, 9999, 10, 2000) == 2000


def test_wac_rounds_half_up_to_whole_xaf():
    # (10*100 + 5*151) / 15 = 1755/15 = 117.0 -> exact; use a .5 case:
    # (1*100 + 1*101)/2 = 100.5 -> 101 (round half up).
    assert weighted_average_cost(1, 100, 1, 101) == 101


# ---------------------------------------------------------------------------
# Stock adjustments never move average_cost (§7A.5)
# ---------------------------------------------------------------------------


def test_add_adjustment_leaves_average_cost_untouched(manager_client, category):
    p = Product.objects.create(
        branch_id=BRANCH_ID, name="Cost basis", category=category,
        retail_price=1000, stock_level=10, average_cost=800, cost_is_set=True,
    )
    resp = manager_client.post(
        "/api/v1/stock-adjustments/",
        {"product": str(p.id), "adjustment_type": "add", "quantity": 5, "reason": "Found more"},
        format="json",
    )
    assert resp.status_code == 201
    p.refresh_from_db()
    assert p.stock_level == 15
    assert p.average_cost == 800  # unchanged — added units inherit the average


def test_remove_adjustment_leaves_average_cost_untouched(manager_client, category):
    p = Product.objects.create(
        branch_id=BRANCH_ID, name="Cost basis 2", category=category,
        retail_price=1000, stock_level=10, average_cost=800, cost_is_set=True,
    )
    resp = manager_client.post(
        "/api/v1/stock-adjustments/",
        {"product": str(p.id), "adjustment_type": "remove", "quantity": -3, "reason": "Damaged"},
        format="json",
    )
    assert resp.status_code == 201
    p.refresh_from_db()
    assert p.stock_level == 7
    assert p.average_cost == 800  # losing units doesn't change what the rest cost


# ---------------------------------------------------------------------------
# Price history (§7A.1)
# ---------------------------------------------------------------------------


def test_create_records_opening_price(manager_client, category):
    resp = manager_client.post(
        "/api/v1/products/",
        {"name": "New", "category": str(category.id), "retail_price": 1500},
        format="json",
    )
    assert resp.status_code == 201
    history = ProductPriceHistory.objects.filter(product_id=resp.data["id"])
    assert history.count() == 1
    assert history.first().retail_price == 1500


def test_price_change_appends_history(manager_client, product):
    before = ProductPriceHistory.objects.filter(product=product).count()
    resp = manager_client.patch(
        f"/api/v1/products/{product.id}/", {"retail_price": 5200}, format="json"
    )
    assert resp.status_code == 200
    rows = ProductPriceHistory.objects.filter(product=product).order_by("created_at")
    assert rows.count() == before + 1
    assert rows.last().retail_price == 5200


def test_non_price_edit_does_not_append_history(manager_client, product):
    before = ProductPriceHistory.objects.filter(product=product).count()
    resp = manager_client.patch(
        f"/api/v1/products/{product.id}/", {"name": "Renamed only"}, format="json"
    )
    assert resp.status_code == 200
    assert ProductPriceHistory.objects.filter(product=product).count() == before


# ---------------------------------------------------------------------------
# Manual cost entry (§7A.8 — owner sets cost for a flagged product)
# ---------------------------------------------------------------------------


def test_creating_with_average_cost_flags_cost_set(manager_client, category):
    resp = manager_client.post(
        "/api/v1/products/",
        {"name": "Opening stock", "category": str(category.id), "retail_price": 1000, "average_cost": 700},
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["average_cost"] == 700
    assert resp.data["cost_is_set"] is True


def test_creating_without_average_cost_is_unset(manager_client, category):
    resp = manager_client.post(
        "/api/v1/products/",
        {"name": "Unknown cost", "category": str(category.id), "retail_price": 1000},
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["average_cost"] == 0
    assert resp.data["cost_is_set"] is False


def test_patching_average_cost_flags_cost_set(manager_client, product):
    assert product.cost_is_set is False
    resp = manager_client.patch(
        f"/api/v1/products/{product.id}/", {"average_cost": 3200}, format="json"
    )
    assert resp.status_code == 200
    product.refresh_from_db()
    assert product.average_cost == 3200
    assert product.cost_is_set is True


def test_cashier_cannot_read_or_set_cost_via_write(cashier_client, product):
    # Cashiers are read-only on products; cost is manager+ like all edits.
    resp = cashier_client.patch(
        f"/api/v1/products/{product.id}/", {"average_cost": 1}, format="json"
    )
    assert resp.status_code == 403
