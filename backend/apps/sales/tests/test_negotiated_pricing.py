"""
Negotiated pricing / haggling (Phase 2 design §3): a cashier may move a
line's price within the allowed band freely, but a discount below the
floor or a surplus above the ceiling needs a manager's PIN approval,
enforced SERVER-side (client bounds are only UX).
"""
import pytest
from django.core.cache import cache

from apps.auth_users.approvals import PURPOSE_PRICE_VARIANCE, issue_approval_token
from apps.auth_users.models import BusinessSettings
from apps.inventory.models import Category, Product
from apps.inventory.services import resolve_price_bounds
from apps.sales.models import SaleLineItem
from apps.sales.services import price_needs_approval

from .conftest import BRANCH_ID, api_client_for

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_cache():
    # verify-pin lockout + BusinessSettings can leak across tests.
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def bounded_product(category):
    """Retail 1000, allows 10% discount and 20% surplus without approval."""
    category.discount_floor_pct = 10
    category.surplus_ceiling_pct = 20
    category.save(update_fields=["discount_floor_pct", "surplus_ceiling_pct"])
    return Product.objects.create(
        branch_id=BRANCH_ID, name="Soap", category=category,
        retail_price=1000, stock_level=100,
    )


def _sell(client, product, quantity, actual_price=None, approval_token=None):
    line = {"product": str(product.id), "quantity": quantity}
    if actual_price is not None:
        line["actual_price"] = actual_price
    body = {"payment_method": "cash", "items": [line]}
    if approval_token is not None:
        body["approval_token"] = approval_token
    return client.post("/api/v1/sales/", body, format="json")


# ---------------------------------------------------------------------------
# Bounds resolution & the pure predicate
# ---------------------------------------------------------------------------


def test_bounds_resolve_product_over_category_over_default(category):
    BusinessSettings.load()  # defaults 0/0
    category.discount_floor_pct = 10
    category.surplus_ceiling_pct = 20
    category.save(update_fields=["discount_floor_pct", "surplus_ceiling_pct"])
    p = Product.objects.create(branch_id=BRANCH_ID, name="X", category=category, retail_price=1000)
    # category wins over the 0/0 default
    assert resolve_price_bounds(p) == (10, 20)
    # product overrides category
    p.discount_floor_pct = 5
    p.save(update_fields=["discount_floor_pct"])
    assert resolve_price_bounds(p) == (5, 20)


def test_price_needs_approval_predicate():
    # 10% floor, 20% ceiling on a 1000 catalogue price.
    assert price_needs_approval(1000, 900, 10, 20) is False   # exactly floor
    assert price_needs_approval(1000, 899, 10, 20) is True    # below floor
    assert price_needs_approval(1000, 1200, 10, 20) is False  # exactly ceiling
    assert price_needs_approval(1000, 1201, 10, 20) is True   # above ceiling
    assert price_needs_approval(1000, 1000, 10, 20) is False  # at catalogue


# ---------------------------------------------------------------------------
# Sale enforcement
# ---------------------------------------------------------------------------


def test_within_bounds_discount_needs_no_approval(cashier_user, bounded_product):
    resp = _sell(api_client_for(cashier_user), bounded_product, 1, actual_price=950)
    assert resp.status_code == 201, resp.data
    line = SaleLineItem.objects.get(sale_id=resp.data["id"])
    assert line.actual_price == 950
    assert line.catalogue_price == 1000
    assert line.variance == -50
    assert line.variance_approved_by_id is None
    # line_total reflects the negotiated price.
    assert line.line_total == 950


def test_beyond_floor_without_token_is_rejected(cashier_user, bounded_product):
    resp = _sell(api_client_for(cashier_user), bounded_product, 1, actual_price=800)  # 20% off
    assert resp.status_code == 400
    assert "approval_token" in resp.data


def test_beyond_floor_with_valid_token_succeeds_and_records_approver(
    cashier_user, manager_user, bounded_product
):
    token = issue_approval_token(manager_user, PURPOSE_PRICE_VARIANCE)
    resp = _sell(api_client_for(cashier_user), bounded_product, 1, actual_price=800, approval_token=token)
    assert resp.status_code == 201, resp.data
    line = SaleLineItem.objects.get(sale_id=resp.data["id"])
    assert line.variance == -200
    assert line.variance_approved_by_id == manager_user.id  # approver recorded


def test_wrong_purpose_token_is_rejected(cashier_user, manager_user, bounded_product):
    from apps.auth_users.approvals import PURPOSE_CREDIT_OVERRIDE
    token = issue_approval_token(manager_user, PURPOSE_CREDIT_OVERRIDE)  # wrong purpose
    resp = _sell(api_client_for(cashier_user), bounded_product, 1, actual_price=800, approval_token=token)
    assert resp.status_code == 400
    assert "approval_token" in resp.data


def test_beyond_ceiling_surplus_needs_approval(cashier_user, manager_user, bounded_product):
    # 1300 is 30% surplus, above the 20% ceiling.
    no_token = _sell(api_client_for(cashier_user), bounded_product, 1, actual_price=1300)
    assert no_token.status_code == 400

    token = issue_approval_token(manager_user, PURPOSE_PRICE_VARIANCE)
    ok = _sell(api_client_for(cashier_user), bounded_product, 1, actual_price=1300, approval_token=token)
    assert ok.status_code == 201, ok.data
    line = SaleLineItem.objects.get(sale_id=ok.data["id"])
    assert line.variance == 300


def test_catalogue_price_is_not_client_trusted(cashier_user, bounded_product):
    """
    Even if a client tries to pass a bogus catalogue_price, the server
    resolves it from the product; only actual_price is client-supplied.
    """
    resp = api_client_for(cashier_user).post(
        "/api/v1/sales/",
        {
            "payment_method": "cash",
            "items": [{"product": str(bounded_product.id), "quantity": 1,
                       "actual_price": 950, "catalogue_price": 1}],  # catalogue_price ignored
        },
        format="json",
    )
    assert resp.status_code == 201
    line = SaleLineItem.objects.get(sale_id=resp.data["id"])
    assert line.catalogue_price == 1000  # server-resolved, not the injected 1


def test_default_bounds_are_strict(cashier_user, category):
    """
    With business defaults 0/0 and no category/product bounds, ANY
    variance needs approval — the safe default.
    """
    p = Product.objects.create(
        branch_id=BRANCH_ID, name="Strict", category=category,
        retail_price=1000, stock_level=10,
    )
    # Category fixture has no bounds set; BusinessSettings default 0/0.
    resp = _sell(api_client_for(cashier_user), p, 1, actual_price=990)  # just 1% off
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Variance summary reporting (§3.4)
# ---------------------------------------------------------------------------


def test_variance_summary_aggregates_surplus_and_discount(
    cashier_user, manager_user, bounded_product
):
    cashier = api_client_for(cashier_user)
    # One discount within bounds (−50 × 2 = −100 discount) ...
    _sell(cashier, bounded_product, 2, actual_price=950)
    # ... and one surplus within bounds (+100 × 1 = +100 surplus).
    _sell(cashier, bounded_product, 1, actual_price=1100)

    resp = api_client_for(manager_user).get("/api/v1/dashboard/variance-summary/?period=today")
    assert resp.status_code == 200
    assert resp.data["total_surplus"] == 100
    assert resp.data["total_discount"] == 100
    assert resp.data["net_variance"] == 0
    # per-cashier breakdown names the culprit.
    rows = resp.data["per_cashier"]
    assert len(rows) == 1
    assert rows[0]["surplus"] == 100
    assert rows[0]["discount"] == 100


def test_variance_summary_is_manager_only(cashier_user):
    resp = api_client_for(cashier_user).get("/api/v1/dashboard/variance-summary/")
    assert resp.status_code == 403
