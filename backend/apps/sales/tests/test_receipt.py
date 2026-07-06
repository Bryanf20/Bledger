import pytest

from .conftest import api_client_for


@pytest.mark.django_db
def test_receipt_returns_pdf(cashier_user, product):
    client = api_client_for(cashier_user)
    sale_resp = client.post(
        "/api/v1/sales/",
        {"payment_method": "cash", "items": [{"product": str(product.id), "quantity": 1}]},
        format="json",
    )
    assert sale_resp.status_code == 201
    sale_id = sale_resp.json()["id"]

    receipt_resp = client.get(f"/api/v1/sales/{sale_id}/receipt/")
    assert receipt_resp.status_code == 200
    assert receipt_resp["Content-Type"] == "application/pdf"
    assert receipt_resp.content.startswith(b"%PDF")


@pytest.mark.django_db
def test_receipt_respects_branch_and_cashier_scoping(cashier_user, manager_user, product):
    owner_client = api_client_for(manager_user)
    sale_resp = owner_client.post(
        "/api/v1/sales/",
        {"payment_method": "cash", "items": [{"product": str(product.id), "quantity": 1}]},
        format="json",
    )
    sale_id = sale_resp.json()["id"]

    other_client = api_client_for(cashier_user)
    response = other_client.get(f"/api/v1/sales/{sale_id}/receipt/")
    assert response.status_code == 404
    