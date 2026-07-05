import pytest

from apps.suppliers.models import Purchase, PurchaseLineItem, Supplier
from apps.sync.models import OutboxEntry

BRANCH_ID = "HQ"


@pytest.fixture
def supplier(db):
    return Supplier.objects.create(branch_id=BRANCH_ID, name="Bafang Distributors")


# -- one-action restock: stock increment + purchase/line-item creation --


@pytest.mark.django_db
def test_recording_purchase_increments_stock(owner_client, supplier, product):
    starting_stock = product.stock_level
    response = owner_client.post(
        "/api/v1/purchases/",
        {
            "supplier": str(supplier.id),
            "purchase_date": "2026-06-01",
            "amount_paid": 0,
            "items": [{"product": str(product.id), "quantity": 50, "unit_cost": 3800}],
        },
        format="json",
    )
    assert response.status_code == 201
    product.refresh_from_db()
    assert product.stock_level == starting_stock + 50


@pytest.mark.django_db
def test_purchase_with_multiple_line_items(owner_client, supplier, product, second_product):
    response = owner_client.post(
        "/api/v1/purchases/",
        {
            "supplier": str(supplier.id),
            "purchase_date": "2026-06-01",
            "amount_paid": 100000,
            "items": [
                {"product": str(product.id), "quantity": 10, "unit_cost": 4000},
                {"product": str(second_product.id), "quantity": 20, "unit_cost": 700},
            ],
        },
        format="json",
    )
    assert response.status_code == 201
    assert response.data["total_amount"] == 10 * 4000 + 20 * 700
    assert PurchaseLineItem.objects.filter(purchase_id=response.data["id"]).count() == 2

    product.refresh_from_db()
    second_product.refresh_from_db()
    assert product.stock_level == 50 + 10
    assert second_product.stock_level == 10 + 20


@pytest.mark.django_db
def test_total_amount_is_computed_not_client_supplied(owner_client, supplier, product):
    response = owner_client.post(
        "/api/v1/purchases/",
        {
            "supplier": str(supplier.id),
            "purchase_date": "2026-06-01",
            "total_amount": 1,  # should be ignored — read-only
            "amount_paid": 0,
            "items": [{"product": str(product.id), "quantity": 5, "unit_cost": 4000}],
        },
        format="json",
    )
    assert response.status_code == 201
    assert response.data["total_amount"] == 20000


@pytest.mark.django_db
def test_recorded_by_is_set_from_request_user(owner_client, owner_user, supplier, product):
    response = owner_client.post(
        "/api/v1/purchases/",
        {
            "supplier": str(supplier.id),
            "purchase_date": "2026-06-01",
            "amount_paid": 0,
            "items": [{"product": str(product.id), "quantity": 5, "unit_cost": 4000}],
        },
        format="json",
    )
    purchase = Purchase.objects.get(pk=response.data["id"])
    assert purchase.recorded_by_id == owner_user.id


# -- payment_status derivation --------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "amount_paid,expected_status",
    [
        (0, Purchase.CREDIT),
        (10000, Purchase.PARTIAL),
        (20000, Purchase.PAID),
        (25000, Purchase.PAID),
    ],
)
def test_payment_status_derived_from_amount_paid(
    owner_client, supplier, product, amount_paid, expected_status
):
    response = owner_client.post(
        "/api/v1/purchases/",
        {
            "supplier": str(supplier.id),
            "purchase_date": "2026-06-01",
            "amount_paid": amount_paid,
            "items": [{"product": str(product.id), "quantity": 5, "unit_cost": 4000}],  # total 20000
        },
        format="json",
    )
    assert response.status_code == 201
    assert response.data["payment_status"] == expected_status


# -- outbox coverage --------------------------------------------------------


@pytest.mark.django_db
def test_purchase_creation_writes_outbox_entry(owner_client, supplier, product):
    response = owner_client.post(
        "/api/v1/purchases/",
        {
            "supplier": str(supplier.id),
            "purchase_date": "2026-06-01",
            "amount_paid": 0,
            "items": [{"product": str(product.id), "quantity": 5, "unit_cost": 4000}],
        },
        format="json",
    )
    purchase_id = response.data["id"]
    entry = OutboxEntry.objects.get(record_id=purchase_id)
    assert entry.operation == OutboxEntry.INSERT
    assert entry.table_name == Purchase._meta.db_table


# -- validation & permissions ----------------------------------------------


@pytest.mark.django_db
def test_purchase_requires_at_least_one_item(owner_client, supplier):
    response = owner_client.post(
        "/api/v1/purchases/",
        {"supplier": str(supplier.id), "purchase_date": "2026-06-01", "items": []},
        format="json",
    )
    assert response.status_code == 400
    assert "items" in response.data


@pytest.mark.django_db
def test_cashier_cannot_record_purchase(cashier_client, supplier, product):
    response = cashier_client.post(
        "/api/v1/purchases/",
        {
            "supplier": str(supplier.id),
            "purchase_date": "2026-06-01",
            "amount_paid": 0,
            "items": [{"product": str(product.id), "quantity": 5, "unit_cost": 4000}],
        },
        format="json",
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_no_patch_or_delete_route_on_purchases(owner_client, supplier, product):
    response = owner_client.post(
        "/api/v1/purchases/",
        {
            "supplier": str(supplier.id),
            "purchase_date": "2026-06-01",
            "amount_paid": 0,
            "items": [{"product": str(product.id), "quantity": 5, "unit_cost": 4000}],
        },
        format="json",
    )
    purchase_id = response.data["id"]
    assert owner_client.patch(f"/api/v1/purchases/{purchase_id}/", {"amount_paid": 99}).status_code == 405
    assert owner_client.delete(f"/api/v1/purchases/{purchase_id}/").status_code == 405


@pytest.mark.django_db
def test_purchases_scoped_to_branch(owner_client, supplier, product):
    other_supplier = Supplier.objects.create(branch_id="OTHER", name="Other Supplier")
    Purchase.objects.create(
        branch_id="OTHER", supplier=other_supplier, purchase_date="2026-06-01",
        total_amount=1000, amount_paid=1000, payment_status=Purchase.PAID,
    )
    response = owner_client.get("/api/v1/purchases/")
    assert response.data["count"] == 0
    