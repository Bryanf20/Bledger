import pytest

from .conftest import api_client_for


@pytest.mark.django_db
def test_cashier_cannot_void(cashier_user, product):
    client = api_client_for(cashier_user)
    create_resp = client.post(
        "/api/v1/sales/", {"payment_method": "cash", "items": [{"product": str(product.id), "quantity": 1}]}, format="json"
    )
    sale_id = create_resp.json()["id"]

    void_resp = client.post(f"/api/v1/sales/{sale_id}/void/", {"void_reason": "test"}, format="json")
    assert void_resp.status_code == 403


@pytest.mark.django_db
def test_manager_can_void_and_stock_restored(manager_user, cashier_user, product):
    cashier_client = api_client_for(cashier_user)
    create_resp = cashier_client.post(
        "/api/v1/sales/", {"payment_method": "cash", "items": [{"product": str(product.id), "quantity": 3}]}, format="json"
    )
    sale_id = create_resp.json()["id"]
    product.refresh_from_db()
    assert product.stock_level == 47

    manager_client = api_client_for(manager_user)
    void_resp = manager_client.post(
        f"/api/v1/sales/{sale_id}/void/", {"void_reason": "customer changed mind"}, format="json"
    )
    assert void_resp.status_code == 200
    assert void_resp.json()["status"] == "voided"

    product.refresh_from_db()
    assert product.stock_level == 50


@pytest.mark.django_db
def test_void_requires_reason(manager_user, cashier_user, product):
    cashier_client = api_client_for(cashier_user)
    create_resp = cashier_client.post(
        "/api/v1/sales/", {"payment_method": "cash", "items": [{"product": str(product.id), "quantity": 1}]}, format="json"
    )
    sale_id = create_resp.json()["id"]

    manager_client = api_client_for(manager_user)
    void_resp = manager_client.post(f"/api/v1/sales/{sale_id}/void/", {}, format="json")
    assert void_resp.status_code == 400
    