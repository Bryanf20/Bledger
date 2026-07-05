import pytest

from .conftest import api_client_for


@pytest.mark.django_db
def test_momo_sale_requires_reference_and_confirmation(cashier_user, product):
    client = api_client_for(cashier_user)
    response = client.post(
        "/api/v1/sales/",
        {"payment_method": "mtn_momo", "items": [{"product": str(product.id), "quantity": 1}]},
        format="json",
    )
    assert response.status_code == 400
    assert "momo_reference" in response.json()


@pytest.mark.django_db
def test_momo_sale_succeeds_with_reference_and_confirmation(cashier_user, product):
    client = api_client_for(cashier_user)
    response = client.post(
        "/api/v1/sales/",
        {
            "payment_method": "mtn_momo",
            "momo_reference": "TXN84739201",
            "momo_confirmed": True,
            "items": [{"product": str(product.id), "quantity": 1}],
        },
        format="json",
    )
    assert response.status_code == 201
    assert response.json()["momo_reference"] == "TXN84739201"
    