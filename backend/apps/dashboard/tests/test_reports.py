import pytest

from apps.dashboard.tests.conftest import make_sale


@pytest.mark.django_db
def test_sales_report_csv(owner_client, owner_user, product):
    make_sale(owner_user, product, quantity=1, unit_price=4500)
    response = owner_client.get("/api/v1/reports/sales/?period=today")
    assert response.status_code == 200
    assert response["Content-Type"] == "text/csv"
    body = response.content
    assert b"Reference" in body


@pytest.mark.django_db
def test_products_report_csv(owner_client, product):
    response = owner_client.get("/api/v1/reports/products/")
    body = response.content
    assert b"Rice 5kg" in body


@pytest.mark.django_db
def test_stock_report_csv(owner_client, low_stock_product):
    response = owner_client.get("/api/v1/reports/stock/")
    body = response.content
    assert b"Sugar 2kg" in body
    assert b"low" in body


@pytest.mark.django_db
def test_reports_pdf_now_available(owner_client, product):
    # apps.printing was stubbed 503 until this session; now that it
    # exists, ?export=pdf succeeds via
    # apps.printing.pdf_backend.render_html_to_pdf().
    response = owner_client.get("/api/v1/reports/products/?export=pdf")
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


@pytest.mark.django_db
def test_reports_require_manager_or_owner(cashier_client):
    response = cashier_client.get("/api/v1/reports/sales/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_reports_require_authentication():
    from rest_framework.test import APIClient
    response = APIClient().get("/api/v1/reports/sales/")
    assert response.status_code in (401, 403)
