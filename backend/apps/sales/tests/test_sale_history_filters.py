"""
Tests for SaleViewSet's history-filtering query params (date_from,
date_to, payment_method, status, search) — added this session for the
Sales History screen. Uses the same api_client_for() fixture pattern
as the rest of apps.sales.tests.
"""
from datetime import date, timedelta

import pytest

from .conftest import api_client_for


@pytest.mark.django_db
def test_date_range_filter(cashier_user, product):
    client = api_client_for(cashier_user)
    resp = client.post(
        "/api/v1/sales/",
        {"payment_method": "cash", "items": [{"product": str(product.id), "quantity": 1}]},
        format="json",
    )
    assert resp.status_code == 201

    today = date.today().isoformat()
    future = (date.today() + timedelta(days=1)).isoformat()

    in_range = client.get(f"/api/v1/sales/?date_from={today}&date_to={today}")
    assert in_range.json()["count"] == 1

    out_of_range = client.get(f"/api/v1/sales/?date_from={future}")
    assert out_of_range.json()["count"] == 0


@pytest.mark.django_db
def test_payment_method_and_status_filters(cashier_user, manager_user, product):
    cashier = api_client_for(cashier_user)
    cashier.post(
        "/api/v1/sales/",
        {"payment_method": "cash", "items": [{"product": str(product.id), "quantity": 1}]},
        format="json",
    )
    momo_resp = cashier.post(
        "/api/v1/sales/",
        {
            "payment_method": "mtn_momo",
            "momo_reference": "TXN1",
            "momo_confirmed": True,
            "items": [{"product": str(product.id), "quantity": 1}],
        },
        format="json",
    )

    manager = api_client_for(manager_user)
    assert manager.get("/api/v1/sales/?payment_method=cash").json()["count"] == 1
    assert manager.get("/api/v1/sales/?payment_method=mtn_momo").json()["count"] == 1

    momo_id = momo_resp.json()["id"]
    manager.post(f"/api/v1/sales/{momo_id}/void/", {"void_reason": "test"}, format="json")

    voided = manager.get("/api/v1/sales/?status=voided")
    assert voided.json()["count"] == 1
    assert voided.json()["results"][0]["id"] == momo_id
    assert manager.get("/api/v1/sales/?status=completed").json()["count"] == 1


@pytest.mark.django_db
def test_search_filters_by_reference(cashier_user, product):
    client = api_client_for(cashier_user)
    create_resp = client.post(
        "/api/v1/sales/",
        {"payment_method": "cash", "items": [{"product": str(product.id), "quantity": 1}]},
        format="json",
    )
    reference = create_resp.json()["reference"]

    assert client.get(f"/api/v1/sales/?search={reference[-4:]}").json()["count"] == 1
    assert client.get("/api/v1/sales/?search=ZZZZ").json()["count"] == 0


@pytest.mark.django_db
def test_invalid_filter_values_are_ignored_not_rejected(cashier_user, product):
    client = api_client_for(cashier_user)
    client.post(
        "/api/v1/sales/",
        {"payment_method": "cash", "items": [{"product": str(product.id), "quantity": 1}]},
        format="json",
    )
    response = client.get("/api/v1/sales/?date_from=not-a-date&payment_method=bitcoin&status=archived")
    assert response.status_code == 200
    assert response.json()["count"] == 1  # every bad filter silently no-ops


@pytest.mark.django_db
def test_cashier_scoping_still_applies_with_filters(cashier_user, manager_user, product):
    cashier = api_client_for(cashier_user)
    cashier.post(
        "/api/v1/sales/",
        {"payment_method": "cash", "items": [{"product": str(product.id), "quantity": 1}]},
        format="json",
    )
    manager = api_client_for(manager_user)
    manager.post(
        "/api/v1/sales/",
        {"payment_method": "cash", "items": [{"product": str(product.id), "quantity": 1}]},
        format="json",
    )
    # Two cash sales exist branch-wide, but the cashier's filtered view
    # only ever sees their own.
    response = cashier.get("/api/v1/sales/?payment_method=cash")
    assert response.json()["count"] == 1
    