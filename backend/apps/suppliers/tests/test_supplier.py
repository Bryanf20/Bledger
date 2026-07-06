import pytest

from apps.suppliers.models import Purchase, Supplier

BRANCH_ID = "HQ"


@pytest.fixture
def supplier(db):
    return Supplier.objects.create(
        branch_id=BRANCH_ID, name="Bafang Distributors", phone="655112233", area="Buea Mile 16"
    )


# -- CRUD & permissions -------------------------------------------------


@pytest.mark.django_db
def test_owner_can_create_supplier(owner_client):
    response = owner_client.post(
        "/api/v1/suppliers/",
        {"name": "Eto'o Supplies", "phone": "677234567", "area": "Buea Town"},
    )
    assert response.status_code == 201
    assert Supplier.objects.filter(name="Eto'o Supplies").exists()


@pytest.mark.django_db
def test_manager_can_create_supplier(manager_client):
    response = manager_client.post("/api/v1/suppliers/", {"name": "New Supplier"})
    assert response.status_code == 201


@pytest.mark.django_db
def test_cashier_cannot_access_suppliers(cashier_client, supplier):
    assert cashier_client.get("/api/v1/suppliers/").status_code == 403
    assert cashier_client.post("/api/v1/suppliers/", {"name": "X"}).status_code == 403


@pytest.mark.django_db
def test_manager_can_patch_supplier(manager_client, supplier):
    response = manager_client.patch(f"/api/v1/suppliers/{supplier.id}/", {"is_active": False})
    assert response.status_code == 200
    supplier.refresh_from_db()
    assert supplier.is_active is False


@pytest.mark.django_db
def test_supplier_list_scoped_to_branch(owner_client, supplier):
    Supplier.objects.create(branch_id="OTHER", name="Other Branch Supplier")
    response = owner_client.get("/api/v1/suppliers/")
    names = [s["name"] for s in response.data["results"]]
    assert "Bafang Distributors" in names
    assert "Other Branch Supplier" not in names


# -- purchase_count / total_spent annotations ----------------------------


@pytest.mark.django_db
def test_new_supplier_has_zero_purchase_stats(owner_client, supplier):
    response = owner_client.get(f"/api/v1/suppliers/{supplier.id}/")
    assert response.data["purchase_count"] == 0
    assert response.data["total_spent"] == 0


@pytest.mark.django_db
def test_purchase_count_and_total_spent_reflect_purchases(owner_client, supplier, product):
    Purchase.objects.create(
        branch_id=BRANCH_ID, supplier=supplier, purchase_date="2026-05-20",
        total_amount=285000, amount_paid=285000, payment_status=Purchase.PAID,
    )
    Purchase.objects.create(
        branch_id=BRANCH_ID, supplier=supplier, purchase_date="2026-05-08",
        total_amount=95000, amount_paid=95000, payment_status=Purchase.PAID,
    )
    response = owner_client.get(f"/api/v1/suppliers/{supplier.id}/")
    assert response.data["purchase_count"] == 2
    assert response.data["total_spent"] == 380000
    