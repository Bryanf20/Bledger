import pytest

from apps.dashboard.tests.conftest import make_sale
from apps.inventory.models import Product
from apps.sales.models import Sale


@pytest.mark.django_db
def test_top_products_ranked_by_revenue(owner_client, owner_user, product, category):
    other_product = Product.objects.create(
        branch_id="HQ", category=category, name="Oil 5L", unit="bottle", retail_price=6000, stock_level=10
    )
    make_sale(owner_user, product, quantity=1, unit_price=1000)  # 1000
    make_sale(owner_user, other_product, quantity=2, unit_price=6000)  # 12000

    response = owner_client.get("/api/v1/dashboard/top-products/?period=today")

    assert response.status_code == 200
    assert response.data[0]["product_name"] == "Oil 5L"
    assert response.data[0]["rank"] == 1
    assert response.data[1]["product_name"] == "Rice 5kg"


@pytest.mark.django_db
def test_top_products_limit_is_capped(owner_client):
    response = owner_client.get("/api/v1/dashboard/top-products/?limit=9999")
    assert response.status_code == 200  # doesn't error, just caps internally


@pytest.mark.django_db
def test_payment_breakdown_groups_by_method(owner_client, owner_user, product):
    make_sale(owner_user, product, quantity=1, unit_price=1000, payment_method=Sale.CASH)
    make_sale(owner_user, product, quantity=1, unit_price=2000, payment_method=Sale.CASH)
    make_sale(owner_user, product, quantity=1, unit_price=500, payment_method=Sale.MTN_MOMO)

    response = owner_client.get("/api/v1/dashboard/payment-breakdown/?period=today")

    by_method = {row["payment_method"]: row for row in response.data}
    assert by_method["cash"]["revenue"] == 3000
    assert by_method["cash"]["transaction_count"] == 2
    assert by_method["mtn_momo"]["revenue"] == 500


@pytest.mark.django_db
def test_manager_can_access_financial_views(manager_client):
    for path in (
        "/api/v1/dashboard/summary/",
        "/api/v1/dashboard/top-products/",
        "/api/v1/dashboard/payment-breakdown/",
        "/api/v1/dashboard/sales-chart/",
    ):
        assert manager_client.get(path).status_code == 200


@pytest.mark.django_db
def test_cashier_cannot_access_financial_views(cashier_client):
    for path in (
        "/api/v1/dashboard/summary/",
        "/api/v1/dashboard/top-products/",
        "/api/v1/dashboard/payment-breakdown/",
        "/api/v1/dashboard/sales-chart/",
    ):
        assert cashier_client.get(path).status_code == 403
