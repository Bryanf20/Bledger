import pytest

from apps.dashboard.tests.conftest import make_sale
from apps.sales.models import Sale


@pytest.mark.django_db
def test_summary_requires_manager_or_owner(cashier_client):
    response = cashier_client.get("/api/v1/dashboard/summary/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_summary_computes_revenue_and_average(owner_client, owner_user, product):
    make_sale(owner_user, product, quantity=2, unit_price=4500)
    make_sale(owner_user, product, quantity=1, unit_price=4500)

    response = owner_client.get("/api/v1/dashboard/summary/?period=today")

    assert response.status_code == 200
    assert response.data["transaction_count"] == 2
    assert response.data["revenue"] == 13500
    assert response.data["average_sale"] == 6750
    assert response.data["top_product_name"] == "Rice 5kg"


@pytest.mark.django_db
def test_summary_excludes_voided_sales(owner_client, owner_user, product):
    make_sale(owner_user, product, quantity=1, unit_price=4500, status=Sale.VOIDED)
    make_sale(owner_user, product, quantity=1, unit_price=4500)

    response = owner_client.get("/api/v1/dashboard/summary/?period=today")

    assert response.data["transaction_count"] == 1
    assert response.data["revenue"] == 4500


@pytest.mark.django_db
def test_summary_unknown_period_defaults_to_today(owner_client, owner_user, product):
    make_sale(owner_user, product, quantity=1, unit_price=4500)
    response = owner_client.get("/api/v1/dashboard/summary/?period=bogus")
    assert response.status_code == 200
    assert response.data["period"] == "today"


@pytest.mark.django_db
def test_summary_zero_sales_returns_zeros_not_error(owner_client):
    response = owner_client.get("/api/v1/dashboard/summary/?period=today")
    assert response.status_code == 200
    assert response.data["revenue"] == 0
    assert response.data["transaction_count"] == 0
    assert response.data["average_sale"] == 0
    assert response.data["top_product_name"] is None
    assert response.data["revenue_change_pct"] is None
