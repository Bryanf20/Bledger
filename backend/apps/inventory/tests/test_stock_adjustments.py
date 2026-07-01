"""
Stock adjustments — design doc Part D: "Never deleted — full audit
trail." add/remove/correction each require a reason and are the only
sanctioned way (besides a future supplier purchase) to move
Product.stock_level directly.
"""
import pytest

from apps.inventory.models import StockAdjustment

pytestmark = pytest.mark.django_db


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


def test_no_update_or_delete_route_exists_for_adjustments(manager_client, product):
    resp = manager_client.post(
        "/api/v1/stock-adjustments/",
        {"product": str(product.id), "adjustment_type": "add", "quantity": 5, "reason": "Restock"},
    )
    adjustment_id = resp.data["id"]

    assert manager_client.patch(f"/api/v1/stock-adjustments/{adjustment_id}/", {"quantity": 99}).status_code == 405
    assert manager_client.delete(f"/api/v1/stock-adjustments/{adjustment_id}/").status_code == 405
    assert StockAdjustment.objects.count() == 1
