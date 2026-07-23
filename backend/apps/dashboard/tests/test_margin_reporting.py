"""
Margin & valuation reporting (Phase 2 design §7A.6): gross margin,
stock valuation, and the low/negative-margin alert. Cost is manager+
financial data, so all three endpoints are manager-only.
"""
import pytest

from apps.inventory.models import Product
from apps.sales.models import Sale, SaleLineItem

from .conftest import BRANCH_ID, make_sale

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Margin summary
# ---------------------------------------------------------------------------


def test_gross_margin_is_revenue_minus_cogs(manager_client, cashier_user, product):
    # 2 @ 4500 sold, COGS 3000 each: revenue 9000, cogs 6000, margin 3000.
    make_sale(cashier_user, product, 2, 4500, unit_cost=3000)
    resp = manager_client.get("/api/v1/dashboard/margin-summary/?period=today")
    assert resp.status_code == 200
    assert resp.data["revenue"] == 9000
    assert resp.data["cogs"] == 6000
    assert resp.data["gross_margin"] == 3000
    assert resp.data["margin_pct"] == pytest.approx(33.3, abs=0.1)


def test_cost_unknown_lines_excluded_from_margin(manager_client, cashier_user, product, category):
    # One costed line (margin known) + one cost-unknown line (excluded).
    make_sale(cashier_user, product, 1, 4500, unit_cost=3000)   # counted
    other = Product.objects.create(
        branch_id=BRANCH_ID, name="Unknown-cost", category=category, retail_price=1000, stock_level=10
    )
    make_sale(cashier_user, other, 1, 1000, unit_cost=0)         # excluded

    resp = manager_client.get("/api/v1/dashboard/margin-summary/?period=today")
    assert resp.data["revenue"] == 4500          # only the costed line
    assert resp.data["gross_margin"] == 1500
    assert resp.data["total_revenue"] == 5500    # both lines
    assert resp.data["uncosted_revenue"] == 1000


def test_voided_sale_excluded_from_margin(manager_client, cashier_user, product):
    make_sale(cashier_user, product, 1, 4500, unit_cost=3000, status=Sale.VOIDED)
    resp = manager_client.get("/api/v1/dashboard/margin-summary/?period=today")
    assert resp.data["gross_margin"] == 0


def test_margin_summary_manager_only(cashier_client):
    assert cashier_client.get("/api/v1/dashboard/margin-summary/").status_code == 403


# ---------------------------------------------------------------------------
# Brokered-sale gains (§7C.4 / step 8f)
# ---------------------------------------------------------------------------


def _brokered_line(cashier, product, qty, price, cost):
    total = qty * price
    sale = Sale.objects.create(
        branch_id=BRANCH_ID, cashier=cashier, payment_method=Sale.CASH,
        subtotal=total, total_amount=total, status=Sale.COMPLETED,
        reference=f"BLD-BR-{Sale.objects.count() + 1:04d}",
    )
    SaleLineItem.objects.create(
        branch_id=BRANCH_ID, sale=sale, product=product, quantity=qty,
        catalogue_price=price, actual_price=price, unit_cost_at_sale=cost,
        line_total=total, is_brokered=True,
    )
    return sale


def test_brokered_gain_is_markup_over_external_cost(manager_client, cashier_user, product):
    # Sourced at 3000, sold at 4000, qty 3 → gain 3000.
    _brokered_line(cashier_user, product, 3, 4000, 3000)
    resp = manager_client.get("/api/v1/dashboard/brokered-summary/?period=today")
    assert resp.status_code == 200
    assert resp.data["revenue"] == 12000
    assert resp.data["cost"] == 9000
    assert resp.data["gain"] == 3000
    assert resp.data["line_count"] == 1


def test_brokered_summary_excludes_normal_lines(manager_client, cashier_user, product):
    make_sale(cashier_user, product, 2, 4500, unit_cost=3000)  # normal, not brokered
    resp = manager_client.get("/api/v1/dashboard/brokered-summary/?period=today")
    assert resp.data["gain"] == 0
    assert resp.data["line_count"] == 0


def test_brokered_summary_manager_only(cashier_client):
    assert cashier_client.get("/api/v1/dashboard/brokered-summary/").status_code == 403


# ---------------------------------------------------------------------------
# Stock valuation
# ---------------------------------------------------------------------------


def test_stock_valuation_sums_costed_products(manager_client, category):
    Product.objects.create(
        branch_id=BRANCH_ID, name="A", category=category, retail_price=1000,
        stock_level=10, average_cost=600, cost_is_set=True,
    )
    Product.objects.create(
        branch_id=BRANCH_ID, name="B", category=category, retail_price=2000,
        stock_level=5, average_cost=1500, cost_is_set=True,
    )
    # Cost-unknown product: counted, not valued.
    Product.objects.create(
        branch_id=BRANCH_ID, name="C", category=category, retail_price=500, stock_level=100,
    )

    resp = manager_client.get("/api/v1/dashboard/stock-valuation/")
    assert resp.status_code == 200
    assert resp.data["stock_value"] == 10 * 600 + 5 * 1500  # 13500
    assert resp.data["costed_products"] == 2
    assert resp.data["cost_unknown_products"] == 1


def test_stock_valuation_manager_only(cashier_client):
    assert cashier_client.get("/api/v1/dashboard/stock-valuation/").status_code == 403


# ---------------------------------------------------------------------------
# Low / negative margin
# ---------------------------------------------------------------------------


def test_low_margin_flags_thin_and_loss_products(manager_client, category):
    # Default margin_alert_pct = 15.
    Product.objects.create(  # healthy 40% — not flagged
        branch_id=BRANCH_ID, name="Healthy", category=category, retail_price=1000,
        stock_level=5, average_cost=600, cost_is_set=True,
    )
    Product.objects.create(  # thin 10% — flagged
        branch_id=BRANCH_ID, name="Thin", category=category, retail_price=1000,
        stock_level=5, average_cost=900, cost_is_set=True,
    )
    Product.objects.create(  # selling at a loss — flagged, at_or_below_cost
        branch_id=BRANCH_ID, name="Loss", category=category, retail_price=1000,
        stock_level=5, average_cost=1200, cost_is_set=True,
    )

    resp = manager_client.get("/api/v1/dashboard/low-margin/")
    assert resp.status_code == 200
    names = [p["name"] for p in resp.data["products"]]
    assert "Healthy" not in names
    assert set(names) == {"Thin", "Loss"}
    # Worst (loss) first.
    assert resp.data["products"][0]["name"] == "Loss"
    assert resp.data["products"][0]["at_or_below_cost"] is True


def test_low_margin_ignores_cost_unknown_products(manager_client, category):
    Product.objects.create(
        branch_id=BRANCH_ID, name="Unknown", category=category, retail_price=1000, stock_level=5,
    )
    resp = manager_client.get("/api/v1/dashboard/low-margin/")
    assert resp.data["products"] == []


def test_low_margin_manager_only(cashier_client):
    assert cashier_client.get("/api/v1/dashboard/low-margin/").status_code == 403
