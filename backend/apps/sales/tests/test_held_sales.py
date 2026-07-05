import pytest

from .conftest import api_client_for


@pytest.mark.django_db
def test_hold_and_restore_sale(cashier_user, product):
    client = api_client_for(cashier_user)
    cart = {"items": [{"product": str(product.id), "quantity": 2}]}

    create_resp = client.post(
        "/api/v1/held-sales/", {"label": "Customer at counter", "cart_data": cart}, format="json"
    )
    assert create_resp.status_code == 201
    held_id = create_resp.json()["id"]

    restore_resp = client.post(f"/api/v1/held-sales/{held_id}/restore/")
    assert restore_resp.status_code == 200
    assert restore_resp.json() == cart

    list_resp = client.get("/api/v1/held-sales/")
    assert list_resp.json()["count"] == 0  # deleted on restore


@pytest.mark.django_db
def test_discard_held_sale(cashier_user, product):
    client = api_client_for(cashier_user)
    cart = {"items": [{"product": str(product.id), "quantity": 1}]}
    create_resp = client.post("/api/v1/held-sales/", {"cart_data": cart}, format="json")
    held_id = create_resp.json()["id"]

    delete_resp = client.delete(f"/api/v1/held-sales/{held_id}/")
    assert delete_resp.status_code == 204
    