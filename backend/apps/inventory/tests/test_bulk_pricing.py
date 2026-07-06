"""
Bulk pricing per Feasibility doc Section 9.2: every product supports an
optional bulk price + quantity threshold. This module tests the
data-layer contract (both must be set together) and the effective-price
resolution used by the POS/dashboard once a branch price override
exists — the actual "apply automatically when cart qty meets threshold"
logic belongs to the not-yet-built sales app, not inventory.
"""
import pytest

pytestmark = pytest.mark.django_db


def test_product_without_bulk_pricing_has_null_bulk_fields(manager_client, category):
    resp = manager_client.post(
        "/api/v1/products/",
        {"name": "No bulk product", "category": str(category.id), "retail_price": 1000},
    )
    assert resp.status_code == 201
    assert resp.data["bulk_price"] is None
    assert resp.data["bulk_min_qty"] is None
    assert resp.data["effective_bulk_price"] is None


def test_product_with_bulk_pricing_round_trips(manager_client, category):
    resp = manager_client.post(
        "/api/v1/products/",
        {
            "name": "Rice carton",
            "category": str(category.id),
            "retail_price": 4500,
            "bulk_price": 4000,
            "bulk_min_qty": 12,
        },
    )
    assert resp.status_code == 201
    assert resp.data["bulk_price"] == 4000
    assert resp.data["bulk_min_qty"] == 12


def test_bulk_price_override_is_independent_of_retail_override(manager_client, product):
    manager_client.post(
        "/api/v1/price-overrides/",
        {"product": str(product.id), "bulk_price_override": 3800},
    )
    resp = manager_client.get(f"/api/v1/products/{product.id}/")
    assert resp.data["effective_bulk_price"] == 3800
    # Retail price falls back to catalogue since no retail override was set.
    assert resp.data["effective_retail_price"] == product.retail_price


def test_removing_bulk_min_qty_while_keeping_bulk_price_is_rejected(manager_client, product):
    resp = manager_client.patch(
        f"/api/v1/products/{product.id}/", {"bulk_min_qty": None}, format="json"
    )
    assert resp.status_code == 400
