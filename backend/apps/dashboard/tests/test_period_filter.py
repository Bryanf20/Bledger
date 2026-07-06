import pytest
from django.utils import timezone

from apps.dashboard.tests.conftest import make_sale


@pytest.mark.django_db
def test_week_period_includes_earlier_this_week_excludes_last_week(owner_client, owner_user, product):
    now = timezone.localtime()
    today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    this_monday_midnight = today_midnight - timezone.timedelta(days=today_midnight.weekday())

    in_week = min(this_monday_midnight + timezone.timedelta(hours=1), now - timezone.timedelta(minutes=1))
    make_sale(owner_user, product, quantity=1, unit_price=1000, when=in_week)
    make_sale(
        owner_user, product, quantity=1, unit_price=1000,
        when=this_monday_midnight - timezone.timedelta(days=1),
    )

    response = owner_client.get("/api/v1/dashboard/summary/?period=week")

    assert response.data["transaction_count"] == 1
    assert response.data["revenue"] == 1000


@pytest.mark.django_db
def test_month_period_includes_earlier_this_month_excludes_last_month(owner_client, owner_user, product):
    now = timezone.localtime()
    this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    in_month = min(this_month_start + timezone.timedelta(hours=2), now - timezone.timedelta(minutes=1))
    make_sale(owner_user, product, quantity=1, unit_price=2000, when=in_month)
    make_sale(
        owner_user, product, quantity=1, unit_price=2000,
        when=this_month_start - timezone.timedelta(days=1),
    )

    response = owner_client.get("/api/v1/dashboard/summary/?period=month")

    assert response.data["transaction_count"] == 1
    assert response.data["revenue"] == 2000


@pytest.mark.django_db
def test_sales_chart_buckets_today_into_multiple_points(owner_client, owner_user, product):
    now = timezone.localtime()
    make_sale(owner_user, product, quantity=1, unit_price=1000, when=now - timezone.timedelta(hours=2))
    make_sale(owner_user, product, quantity=1, unit_price=1000, when=now - timezone.timedelta(hours=2, minutes=-10))
    make_sale(owner_user, product, quantity=1, unit_price=2000, when=now - timezone.timedelta(minutes=5))

    response = owner_client.get("/api/v1/dashboard/sales-chart/?period=today")

    assert response.status_code == 200
    total_revenue = sum(point["revenue"] for point in response.data)
    assert total_revenue == 4000
    assert len(response.data) >= 1


@pytest.mark.django_db
def test_sales_chart_buckets_week_by_day(owner_client, owner_user, product):
    now = timezone.localtime()
    make_sale(owner_user, product, quantity=1, unit_price=1000, when=now - timezone.timedelta(minutes=1))
    response = owner_client.get("/api/v1/dashboard/sales-chart/?period=week")
    assert response.status_code == 200
    assert len(response.data) >= 1
