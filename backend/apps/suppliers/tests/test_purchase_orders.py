"""
Purchase orders (Phase 2 design §6). A PO touches no stock; receiving it
creates a Purchase through the single stock-moving path and advances the PO.
"""
import pytest
from django.urls import reverse

from apps.suppliers.models import (
    Purchase,
    PurchaseOrder,
    Supplier,
)

BRANCH_ID = "HQ"
LIST_URL = reverse("purchase-order-list")


@pytest.fixture
def supplier(db):
    return Supplier.objects.create(branch_id=BRANCH_ID, name="Eto'o Supplies")


@pytest.mark.django_db
def test_cashier_cannot_access_purchase_orders(cashier_client):
    assert cashier_client.get(LIST_URL).status_code == 403


@pytest.mark.django_db
def test_create_po_does_not_touch_stock(manager_client, supplier, product):
    before = product.stock_level
    resp = manager_client.post(
        LIST_URL,
        {"supplier": str(supplier.id), "order_date": "2026-07-27", "status": "sent",
         "items": [{"product": str(product.id), "quantity_ordered": 20, "unit_cost": 3000}]},
        format="json",
    )
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert body["status"] == "sent"
    assert body["total_ordered_amount"] == 60000

    product.refresh_from_db()
    assert product.stock_level == before  # a PO never moves stock


@pytest.mark.django_db
def test_receive_full_creates_purchase_and_increments_stock(manager_client, supplier, product):
    before = product.stock_level
    po = manager_client.post(
        LIST_URL,
        {"supplier": str(supplier.id), "order_date": "2026-07-27", "status": "sent",
         "items": [{"product": str(product.id), "quantity_ordered": 20, "unit_cost": 3000}]},
        format="json",
    ).json()
    line_id = po["line_items"][0]["id"]

    receive_url = reverse("purchase-order-receive", args=[po["id"]])
    resp = manager_client.post(
        receive_url,
        {"receipts": [{"line": line_id, "quantity": 20}], "amount_paid": 60000},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["status"] == "received"
    assert body["line_items"][0]["quantity_received"] == 20
    assert len(body["receipt_ids"]) == 1

    product.refresh_from_db()
    assert product.stock_level == before + 20          # stock moved via the Purchase path
    purchase = Purchase.objects.get(id=body["receipt_ids"][0])
    assert purchase.purchase_order_id is not None
    assert purchase.total_amount == 60000


@pytest.mark.django_db
def test_partial_receipt_sets_partially_received(manager_client, supplier, product):
    po = manager_client.post(
        LIST_URL,
        {"supplier": str(supplier.id), "order_date": "2026-07-27", "status": "sent",
         "items": [{"product": str(product.id), "quantity_ordered": 20, "unit_cost": 3000}]},
        format="json",
    ).json()
    line_id = po["line_items"][0]["id"]
    receive_url = reverse("purchase-order-receive", args=[po["id"]])

    resp = manager_client.post(
        receive_url, {"receipts": [{"line": line_id, "quantity": 15}]}, format="json"
    )
    assert resp.status_code == 200, resp.content
    assert resp.json()["status"] == "partially_received"
    assert resp.json()["line_items"][0]["quantity_received"] == 15
    assert resp.json()["line_items"][0]["outstanding"] == 5


@pytest.mark.django_db
def test_cannot_receive_more_than_outstanding(manager_client, supplier, product):
    po = manager_client.post(
        LIST_URL,
        {"supplier": str(supplier.id), "order_date": "2026-07-27", "status": "sent",
         "items": [{"product": str(product.id), "quantity_ordered": 20, "unit_cost": 3000}]},
        format="json",
    ).json()
    line_id = po["line_items"][0]["id"]
    receive_url = reverse("purchase-order-receive", args=[po["id"]])
    resp = manager_client.post(
        receive_url, {"receipts": [{"line": line_id, "quantity": 25}]}, format="json"
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_send_and_cancel_transitions(manager_client, supplier, product):
    po = manager_client.post(
        LIST_URL,
        {"supplier": str(supplier.id), "order_date": "2026-07-27",
         "items": [{"product": str(product.id), "quantity_ordered": 5, "unit_cost": 1000}]},
        format="json",
    ).json()
    assert po["status"] == "draft"

    send_url = reverse("purchase-order-send", args=[po["id"]])
    assert manager_client.post(send_url).json()["status"] == "sent"

    cancel_url = reverse("purchase-order-cancel", args=[po["id"]])
    assert manager_client.post(cancel_url).json()["status"] == "cancelled"

    # A cancelled PO can't be received.
    PurchaseOrder.objects.get(id=po["id"])
    line_id = po["line_items"][0]["id"]
    receive_url = reverse("purchase-order-receive", args=[po["id"]])
    assert manager_client.post(
        receive_url, {"receipts": [{"line": line_id, "quantity": 1}]}, format="json"
    ).status_code == 400


@pytest.mark.django_db
def test_po_writes_outbox_entries(manager_client, supplier, product):
    from apps.sync.models import OutboxEntry

    manager_client.post(
        LIST_URL,
        {"supplier": str(supplier.id), "order_date": "2026-07-27",
         "items": [{"product": str(product.id), "quantity_ordered": 5, "unit_cost": 1000}]},
        format="json",
    )
    assert OutboxEntry.objects.filter(table_name="suppliers_purchaseorder").exists()
    assert OutboxEntry.objects.filter(table_name="suppliers_purchaseorderlineitem").exists()
