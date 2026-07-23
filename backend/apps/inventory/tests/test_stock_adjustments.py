"""
Stock adjustments — design doc Part D: "Never deleted — full audit
trail." add/remove/correction each require a reason and are the only
sanctioned way (besides a future supplier purchase) to move
Product.stock_level directly.
"""
import pytest

from apps.inventory.models import Product, StockAdjustment

pytestmark = pytest.mark.django_db


@pytest.fixture
def costed_product(branch, category):
    """A product with a known cost basis, so a damage removal has a value
    to write off (step 8d)."""
    from apps.inventory.tests.conftest import BRANCH_ID

    return Product.objects.create(
        branch_id=BRANCH_ID,
        name="Peak milk tin",
        category=category,
        unit="tin",
        retail_price=1000,
        stock_level=50,
        low_stock_threshold=5,
        average_cost=800,
        cost_is_set=True,
    )


def test_add_adjustment_increases_stock_and_snapshots(manager_client, manager_user, product):
    resp = manager_client.post(
        "/api/v1/stock-adjustments/",
        {
            "product": str(product.id),
            "adjustment_type": "add",
            "quantity": 10,
            "reason": "Restock from supplier",
        },
    )
    assert resp.status_code == 201
    assert resp.data["stock_before"] == 20
    assert resp.data["stock_after"] == 30
    assert resp.data["adjusted_by"] == manager_user.id

    product.refresh_from_db()
    assert product.stock_level == 30


def test_remove_adjustment_decreases_stock(manager_client, product):
    resp = manager_client.post(
        "/api/v1/stock-adjustments/",
        {
            "product": str(product.id),
            "adjustment_type": "remove",
            "quantity": -5,
            "reason": "Damaged in storage",
        },
    )
    assert resp.status_code == 201
    product.refresh_from_db()
    assert product.stock_level == 15


def test_add_adjustment_with_negative_quantity_is_rejected(manager_client, product):
    resp = manager_client.post(
        "/api/v1/stock-adjustments/",
        {"product": str(product.id), "adjustment_type": "add", "quantity": -5, "reason": "Restock"},
    )
    assert resp.status_code == 400


def test_remove_adjustment_with_positive_quantity_is_rejected(manager_client, product):
    resp = manager_client.post(
        "/api/v1/stock-adjustments/",
        {"product": str(product.id), "adjustment_type": "remove", "quantity": 5, "reason": "Damaged"},
    )
    assert resp.status_code == 400


def test_adjustment_without_reason_is_rejected(manager_client, product):
    resp = manager_client.post(
        "/api/v1/stock-adjustments/",
        {"product": str(product.id), "adjustment_type": "add", "quantity": 5, "reason": "   "},
    )
    assert resp.status_code == 400


def test_correction_adjustment_can_go_either_direction(manager_client, product):
    resp = manager_client.post(
        "/api/v1/stock-adjustments/",
        {
            "product": str(product.id),
            "adjustment_type": "correction",
            "quantity": -3,
            "reason": "Physical count discrepancy",
        },
    )
    assert resp.status_code == 201
    product.refresh_from_db()
    assert product.stock_level == 17


def test_cashier_cannot_create_adjustment(cashier_client, product):
    resp = cashier_client.post(
        "/api/v1/stock-adjustments/",
        {"product": str(product.id), "adjustment_type": "add", "quantity": 5, "reason": "Restock"},
    )
    assert resp.status_code == 403


def test_cashier_can_read_adjustment_history(cashier_client, manager_client, product):
    manager_client.post(
        "/api/v1/stock-adjustments/",
        {"product": str(product.id), "adjustment_type": "add", "quantity": 5, "reason": "Restock"},
    )
    resp = cashier_client.get("/api/v1/stock-adjustments/")
    assert resp.status_code == 200
    assert resp.data["count"] == 1


# ---------------------------------------------------------------------------
# Damage/expiry -> Losses expense booking (step 8d)
# ---------------------------------------------------------------------------


def test_damage_removal_books_loss_expense_at_cost(manager_client, manager_user, costed_product):
    from apps.finances.models import CashbookEntry

    resp = manager_client.post(
        "/api/v1/stock-adjustments/",
        {
            "product": str(costed_product.id),
            "adjustment_type": "remove",
            "quantity": -5,
            "reason": "Expired stock",
            "book_as_expense": True,
        },
    )
    assert resp.status_code == 201
    entry = CashbookEntry.objects.get(source_adjustment=resp.data["id"])
    assert entry.direction == CashbookEntry.EXPENSE
    assert entry.category.name == "Losses/Damage"
    assert entry.amount == 5 * 800  # |qty| × average_cost
    assert entry.recorded_by_id == manager_user.id
    assert resp.data["booked_expense_amount"] == 4000


def test_confirmed_amount_overrides_computed_cost(manager_client, costed_product):
    from apps.finances.models import CashbookEntry

    resp = manager_client.post(
        "/api/v1/stock-adjustments/",
        {
            "product": str(costed_product.id),
            "adjustment_type": "remove",
            "quantity": -2,
            "reason": "Broken bottles",
            "book_as_expense": True,
            "expense_amount": 1500,  # user edited the default (would have been 1600)
        },
    )
    assert resp.status_code == 201
    entry = CashbookEntry.objects.get(source_adjustment=resp.data["id"])
    assert entry.amount == 1500


def test_book_as_expense_rejected_for_add(manager_client, costed_product):
    resp = manager_client.post(
        "/api/v1/stock-adjustments/",
        {
            "product": str(costed_product.id),
            "adjustment_type": "add",
            "quantity": 5,
            "reason": "Restock",
            "book_as_expense": True,
        },
    )
    assert resp.status_code == 400


def test_cost_unknown_product_books_no_expense(manager_client, product):
    """No cost basis => nothing to write off, so no cashbook entry even
    when booking is requested."""
    from apps.finances.models import CashbookEntry

    resp = manager_client.post(
        "/api/v1/stock-adjustments/",
        {
            "product": str(product.id),
            "adjustment_type": "remove",
            "quantity": -5,
            "reason": "Damaged",
            "book_as_expense": True,
        },
    )
    assert resp.status_code == 201
    assert CashbookEntry.objects.count() == 0
    assert resp.data["booked_expense_amount"] is None


def test_remove_without_booking_creates_no_expense(manager_client, costed_product):
    from apps.finances.models import CashbookEntry

    resp = manager_client.post(
        "/api/v1/stock-adjustments/",
        {
            "product": str(costed_product.id),
            "adjustment_type": "remove",
            "quantity": -5,
            "reason": "Damaged",
        },
    )
    assert resp.status_code == 201
    assert CashbookEntry.objects.count() == 0


def test_no_update_or_delete_route_exists_for_adjustments(manager_client, product):
    resp = manager_client.post(
        "/api/v1/stock-adjustments/",
        {"product": str(product.id), "adjustment_type": "add", "quantity": 5, "reason": "Restock"},
    )
    adjustment_id = resp.data["id"]

    assert manager_client.patch(f"/api/v1/stock-adjustments/{adjustment_id}/", {"quantity": 99}).status_code == 405
    assert manager_client.delete(f"/api/v1/stock-adjustments/{adjustment_id}/").status_code == 405
    assert StockAdjustment.objects.count() == 1
