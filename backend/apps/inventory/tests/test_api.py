import pytest

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------

def test_cashier_can_list_products(cashier_client, product):
    resp = cashier_client.get("/api/v1/products/")
    assert resp.status_code == 200
    assert resp.data["count"] == 1


def test_cashier_cannot_create_product(cashier_client, category):
    resp = cashier_client.post(
        "/api/v1/products/",
        {"name": "New product", "category": str(category.id), "retail_price": 1000},
    )
    assert resp.status_code == 403


def test_manager_can_create_product(manager_client, category):
    resp = manager_client.post(
        "/api/v1/products/",
        {"name": "New product", "category": str(category.id), "retail_price": 1000},
    )
    assert resp.status_code == 201
    assert resp.data["source"] == "manual"
    assert resp.data["stock_level"] == 0


def test_owner_can_patch_product(owner_client, product):
    resp = owner_client.patch(f"/api/v1/products/{product.id}/", {"retail_price": 5000})
    assert resp.status_code == 200
    assert resp.data["retail_price"] == 5000


def test_cashier_cannot_patch_product(cashier_client, product):
    resp = cashier_client.patch(f"/api/v1/products/{product.id}/", {"retail_price": 5000})
    assert resp.status_code == 403


def test_deleting_a_product_deactivates_not_deletes(manager_client, product):
    resp = manager_client.delete(f"/api/v1/products/{product.id}/")
    assert resp.status_code == 204
    product.refresh_from_db()
    assert product.is_active is False


def test_creating_product_without_bulk_min_qty_but_with_bulk_price_fails(manager_client, category):
    resp = manager_client.post(
        "/api/v1/products/",
        {"name": "Bad bulk", "category": str(category.id), "retail_price": 1000, "bulk_price": 900},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------

def test_manager_can_create_category(manager_client):
    resp = manager_client.post("/api/v1/categories/", {"name": "Drinks", "sort_order": 1})
    assert resp.status_code == 201


def test_cashier_cannot_create_category(cashier_client):
    resp = cashier_client.post("/api/v1/categories/", {"name": "Drinks"})
    assert resp.status_code == 403


def test_unauthenticated_request_is_rejected(product):
    from rest_framework.test import APIClient

    resp = APIClient().get("/api/v1/products/")
    assert resp.status_code == 401


# ---------------------------------------------------------------------
# Price overrides
# ---------------------------------------------------------------------

def test_manager_can_set_price_override(manager_client, manager_user, product):
    resp = manager_client.post(
        "/api/v1/price-overrides/",
        {"product": str(product.id), "retail_price_override": 5200},
    )
    assert resp.status_code == 201
    assert resp.data["set_by"] == manager_user.id


def test_price_override_upserts_on_second_call(manager_client, product):
    manager_client.post("/api/v1/price-overrides/", {"product": str(product.id), "retail_price_override": 5200})
    resp = manager_client.post(
        "/api/v1/price-overrides/", {"product": str(product.id), "retail_price_override": 5300}
    )
    assert resp.status_code == 201

    from apps.inventory.models import BranchPriceOverride

    assert BranchPriceOverride.objects.filter(product=product).count() == 1
    assert BranchPriceOverride.objects.get(product=product).retail_price_override == 5300


def test_cashier_cannot_set_price_override(cashier_client, product):
    resp = cashier_client.post(
        "/api/v1/price-overrides/", {"product": str(product.id), "retail_price_override": 5200}
    )
    assert resp.status_code == 403


def test_product_list_reflects_effective_price_after_override(manager_client, product):
    manager_client.post("/api/v1/price-overrides/", {"product": str(product.id), "retail_price_override": 5200})
    resp = manager_client.get(f"/api/v1/products/{product.id}/")
    assert resp.data["effective_retail_price"] == 5200
    # Underlying catalogue price is untouched.
    assert resp.data["retail_price"] == 4500
