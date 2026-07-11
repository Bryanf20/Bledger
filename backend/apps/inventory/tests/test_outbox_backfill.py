"""
Tests for the outbox backfill added this session -- StockAdjustment,
BranchPriceOverride, and Product deactivation now each write an
OutboxEntry, matching apps.suppliers/apps.sales's existing coverage.
Self-contained fixtures, same pattern as apps.suppliers.tests.conftest
(which itself mirrors apps.sales.tests.conftest) -- not importing
apps.inventory.tests.conftest directly since this project's convention
is per-test-file fixture independence rather than assuming another
file's conftest shape without verifying it first.
"""
import pytest
from rest_framework.test import APIClient

from apps.auth_users.models import Branch, BledgerUser
from apps.inventory.models import Category, Product
from apps.sync.models import OutboxEntry

BRANCH_ID = "HQ"


@pytest.fixture
def branch(db):
    return Branch.objects.create(
        business_name="Tabi Provisions",
        branch_name="Buea Main Branch",
        address="Molyko, Buea",
        phone="677123456",
        deployment_mode="standalone",
        setup_complete=True,
    )


@pytest.fixture
def manager_user(db, branch):
    return BledgerUser.objects.create_user(
        branch=branch, name="Manny Manager", username="manager1", role="manager", password="managerpass123"
    )


@pytest.fixture
def category(db):
    return Category.objects.create(branch_id=BRANCH_ID, name="Grains", sort_order=1)


@pytest.fixture
def product(db, category):
    return Product.objects.create(
        branch_id=BRANCH_ID,
        name="Mama Gold rice 5kg",
        category=category,
        unit="bag",
        retail_price=4500,
        stock_level=50,
        low_stock_threshold=5,
    )


@pytest.fixture
def manager_client(manager_user):
    client = APIClient()
    client.force_authenticate(user=manager_user)
    return client


@pytest.mark.django_db
def test_stock_adjustment_writes_outbox_entry(manager_client, product):
    resp = manager_client.post(
        "/api/v1/stock-adjustments/",
        {"product": str(product.id), "adjustment_type": "add", "quantity": 10, "reason": "Restock"},
        format="json",
    )
    assert resp.status_code == 201

    entry = OutboxEntry.objects.filter(record_id=resp.data["id"]).first()
    assert entry is not None
    assert entry.operation == OutboxEntry.INSERT
    assert entry.branch_id == BRANCH_ID


@pytest.mark.django_db
def test_price_override_insert_then_update_writes_correct_operations(manager_client, product):
    first = manager_client.post(
        "/api/v1/price-overrides/",
        {"product": str(product.id), "retail_price_override": 4200},
        format="json",
    )
    assert first.status_code == 201
    first_entry = OutboxEntry.objects.filter(record_id=first.data["id"]).order_by("created_at").first()
    assert first_entry.operation == OutboxEntry.INSERT

    second = manager_client.post(
        "/api/v1/price-overrides/",
        {"product": str(product.id), "retail_price_override": 4100},
        format="json",
    )
    assert second.status_code == 201
    # UPSERT -- same override row, so same id as the first write.
    assert second.data["id"] == first.data["id"]
    second_entry = OutboxEntry.objects.filter(record_id=second.data["id"]).order_by("created_at").last()
    assert second_entry.operation == OutboxEntry.UPDATE


@pytest.mark.django_db
def test_product_deactivation_writes_outbox_entry(manager_client, product):
    resp = manager_client.delete(f"/api/v1/products/{product.id}/")
    assert resp.status_code == 204

    entry = OutboxEntry.objects.filter(record_id=product.id).order_by("created_at").last()
    assert entry is not None
    assert entry.operation == OutboxEntry.UPDATE
    assert entry.branch_id == BRANCH_ID
