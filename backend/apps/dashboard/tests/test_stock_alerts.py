import pytest


@pytest.mark.django_db
def test_stock_alerts_visible_to_cashier(cashier_client, low_stock_product, out_of_stock_product):
    response = cashier_client.get("/api/v1/dashboard/stock-alerts/")
    assert response.status_code == 200
    names = {row["product_name"] for row in response.data}
    assert "Sugar 2kg" in names
    assert "Maggi cube" in names


@pytest.mark.django_db
def test_stock_alerts_excludes_healthy_stock(cashier_client, product, low_stock_product):
    response = cashier_client.get("/api/v1/dashboard/stock-alerts/")
    names = {row["product_name"] for row in response.data}
    assert "Rice 5kg" not in names  # stock_level 20 > threshold 5
    assert "Sugar 2kg" in names


@pytest.mark.django_db
def test_stock_alerts_status_labels(cashier_client, low_stock_product, out_of_stock_product):
    response = cashier_client.get("/api/v1/dashboard/stock-alerts/")
    by_name = {row["product_name"]: row["status"] for row in response.data}
    assert by_name["Sugar 2kg"] == "low"
    assert by_name["Maggi cube"] == "out"


@pytest.mark.django_db
def test_stock_alerts_available_to_owner_and_manager_too(owner_client, manager_client, low_stock_product):
    assert owner_client.get("/api/v1/dashboard/stock-alerts/").status_code == 200
    assert manager_client.get("/api/v1/dashboard/stock-alerts/").status_code == 200


@pytest.mark.django_db
def test_stock_alerts_requires_authentication():
    from rest_framework.test import APIClient
    response = APIClient().get("/api/v1/dashboard/stock-alerts/")
    assert response.status_code in (401, 403)
