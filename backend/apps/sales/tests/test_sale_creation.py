import pytest

from .conftest import api_client_for


@pytest.mark.django_db
def test_cashier_can_create_cash_sale(cashier_user, product):
    client = api_client_for(cashier_user)
    response = client.post(
        "/api/v1/sales/",
        {
            "payment_method": "cash",
            "amount_tendered": 10000,
            "items": [{"product": str(product.id), "quantity": 2}],
        },
        format="json",
    )
    assert response.status_code == 201
    data = response.json()
    assert data["total_amount"] == 9000
    assert data["reference"].startswith("BLD-")

    product.refresh_from_db()
    assert product.stock_level == 48


@pytest.mark.django_db
def test_bulk_price_applies_at_threshold(cashier_user, product):
    client = api_client_for(cashier_user)
    response = client.post(
        "/api/v1/sales/",
        {"payment_method": "cash", "items": [{"product": str(product.id), "quantity": 12}]},
        format="json",
    )
    assert response.status_code == 201
    assert response.json()["total_amount"] == 4000 * 12


@pytest.mark.django_db
def test_insufficient_stock_rejected(cashier_user, product):
    client = api_client_for(cashier_user)
    response = client.post(
        "/api/v1/sales/",
        {"payment_method": "cash", "items": [{"product": str(product.id), "quantity": 999}]},
        format="json",
    )
    assert response.status_code == 400
    product.refresh_from_db()
    assert product.stock_level == 50  # unchanged — transaction rolled back
    