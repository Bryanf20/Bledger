"""
Cloud POST /api/v1/sync/push/ — durable, idempotent receipt of branch
writes with per-entry results (Phase 2 design §2.4, §2.5).

Apply-mechanism tests use branch-owned tables (Customer / CustomerPayment):
HQ-owned catalogue (Category/Product) is pull-only and a push of it is
rejected — asserted separately in test_catalogue_push_is_rejected.
"""
import datetime
import uuid

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.auth_users.models import Branch
from apps.customers.models import Customer, CustomerPayment
from apps.sync.models import AppliedEntry
from apps.sync.utils import serialize_instance

PUSH_URL = reverse("sync-push")


@pytest.fixture
def device_branch(db):
    return Branch.objects.create(
        business_name="Tabi Provisions", branch_name="Limbe Branch",
        phone="699000000", code="LMB",
        deployment_mode=Branch.DEPLOYMENT_CONNECTED, setup_complete=True,
        sync_token="dev-token",
    )


@pytest.fixture
def bid(device_branch):
    return str(device_branch.id)


@pytest.fixture
def device_client(device_branch):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION="SyncToken dev-token")
    return c


def entry_for(instance, operation="insert", outbox_id=None):
    return {
        "outbox_id": str(outbox_id or uuid.uuid4()),
        "table_name": instance._meta.db_table,
        "record_id": str(instance.id),
        "operation": operation,
        "payload": serialize_instance(instance),
        "schema_version": 1,
    }


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_push_requires_a_device_token():
    resp = APIClient().post(PUSH_URL, {"entries": []}, format="json")
    assert resp.status_code in (401, 403)


@pytest.mark.django_db
def test_push_rejects_unknown_token():
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION="SyncToken nope")
    assert c.post(PUSH_URL, {"entries": []}, format="json").status_code == 401


@pytest.mark.django_db
def test_deactivated_branch_cannot_push(device_branch, device_client):
    Branch.objects.filter(pk=device_branch.pk).update(is_active=False)
    assert device_client.post(PUSH_URL, {"entries": []}, format="json").status_code in (401, 403)


# ---------------------------------------------------------------------------
# Applying (branch-owned tables)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_push_applies_a_new_record(bid, device_client):
    cust = Customer.objects.create(branch_id=bid, name="Mama Ada")
    entry = entry_for(cust)
    Customer.all_objects.filter(pk=cust.id).delete()  # not on the cloud yet

    resp = device_client.post(PUSH_URL, {"entries": [entry]}, format="json")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["results"][0]["status"] == "applied"
    assert body["applied"] == 1
    assert "server_time" in body

    recreated = Customer.all_objects.get(pk=cust.id)
    assert recreated.name == "Mama Ada"
    assert AppliedEntry.objects.filter(outbox_id=entry["outbox_id"]).count() == 1


@pytest.mark.django_db
def test_push_applies_record_with_foreign_key(bid, device_client):
    cust = Customer.objects.create(branch_id=bid, name="Mama Ada")
    pay = CustomerPayment.objects.create(
        branch_id=bid, customer=cust, amount=2000,
        payment_date=datetime.date(2026, 7, 24), recorded_by=None,
    )
    entry = entry_for(pay)
    CustomerPayment.all_objects.filter(pk=pay.id).delete()

    resp = device_client.post(PUSH_URL, {"entries": [entry]}, format="json")
    assert resp.status_code == 200, resp.content
    assert resp.json()["results"][0]["status"] == "applied"

    recreated = CustomerPayment.all_objects.get(pk=pay.id)
    assert recreated.customer_id == cust.id
    assert recreated.amount == 2000


@pytest.mark.django_db
def test_push_is_idempotent(bid, device_client):
    cust = Customer.objects.create(branch_id=bid, name="Mama Ada")
    entry = entry_for(cust)
    Customer.all_objects.filter(pk=cust.id).delete()

    first = device_client.post(PUSH_URL, {"entries": [entry]}, format="json")
    second = device_client.post(PUSH_URL, {"entries": [entry]}, format="json")

    assert first.json()["results"][0]["status"] == "applied"
    assert second.json()["results"][0]["status"] == "duplicate"
    assert AppliedEntry.objects.filter(outbox_id=entry["outbox_id"]).count() == 1


@pytest.mark.django_db
def test_update_preserves_branch_version_and_does_not_bump(bid, device_client):
    cust = Customer.objects.create(branch_id=bid, name="Mama Ada")
    payload = serialize_instance(cust)
    payload["name"] = "Mama Adaeze"
    payload["version"] = 5
    entry = {
        "outbox_id": str(uuid.uuid4()), "table_name": cust._meta.db_table,
        "record_id": str(cust.id), "operation": "update", "payload": payload,
        "schema_version": 1,
    }

    resp = device_client.post(PUSH_URL, {"entries": [entry]}, format="json")
    assert resp.json()["results"][0]["status"] == "applied"

    cust.refresh_from_db()
    assert cust.name == "Mama Adaeze"
    assert cust.version == 5  # from payload, not incremented to 2


@pytest.mark.django_db
def test_delete_operation_applies_soft_delete_tombstone(bid, device_client):
    cust = Customer.objects.create(branch_id=bid, name="Mama Ada")
    cust.soft_delete()
    payload = serialize_instance(cust)  # deleted_at set
    entry = {
        "outbox_id": str(uuid.uuid4()), "table_name": cust._meta.db_table,
        "record_id": str(cust.id), "operation": "delete", "payload": payload,
        "schema_version": 1,
    }
    Customer.all_objects.filter(pk=cust.id).delete()

    resp = device_client.post(PUSH_URL, {"entries": [entry]}, format="json")
    assert resp.json()["results"][0]["status"] == "applied"

    row = Customer.all_objects.get(pk=cust.id)
    assert row.deleted_at is not None
    assert not Customer.objects.filter(pk=cust.id).exists()  # hidden by soft-delete manager


# ---------------------------------------------------------------------------
# Rejections (permanent)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_catalogue_push_is_rejected(bid, device_client):
    """§2.5 — HQ-owned catalogue is pull-only; a branch may not push it."""
    for table in ("inventory_product", "inventory_category"):
        entry = {
            "outbox_id": str(uuid.uuid4()), "table_name": table,
            "record_id": str(uuid.uuid4()), "operation": "update",
            "payload": {"id": str(uuid.uuid4()), "branch_id": bid, "name": "X"},
            "schema_version": 1,
        }
        r = device_client.post(PUSH_URL, {"entries": [entry]}, format="json").json()
        assert r["results"][0]["status"] == "rejected", table
        assert "catalogue" in r["results"][0]["error"].lower()


@pytest.mark.django_db
def test_never_synced_table_is_rejected(bid, device_client):
    entry = {
        "outbox_id": str(uuid.uuid4()), "table_name": "sales_heldsale",
        "record_id": str(uuid.uuid4()), "operation": "insert",
        "payload": {"id": str(uuid.uuid4()), "branch_id": bid}, "schema_version": 1,
    }
    body = device_client.post(PUSH_URL, {"entries": [entry]}, format="json").json()
    assert body["results"][0]["status"] == "rejected"
    assert body["rejected"] == 1


@pytest.mark.django_db
def test_unregistered_table_is_rejected(bid, device_client):
    entry = {
        "outbox_id": str(uuid.uuid4()), "table_name": "made_up_table",
        "record_id": str(uuid.uuid4()), "operation": "insert",
        "payload": {"id": str(uuid.uuid4()), "branch_id": bid}, "schema_version": 1,
    }
    body = device_client.post(PUSH_URL, {"entries": [entry]}, format="json").json()
    assert body["results"][0]["status"] == "rejected"


@pytest.mark.django_db
def test_branch_id_mismatch_is_rejected(device_client):
    entry = {
        "outbox_id": str(uuid.uuid4()), "table_name": "customers_customer",
        "record_id": str(uuid.uuid4()), "operation": "insert",
        "payload": {"id": str(uuid.uuid4()), "branch_id": "SOME-OTHER-BRANCH",
                    "name": "X"}, "schema_version": 1,
    }
    body = device_client.post(PUSH_URL, {"entries": [entry]}, format="json").json()
    assert body["results"][0]["status"] == "rejected"
    assert "branch" in body["results"][0]["error"].lower()


@pytest.mark.django_db
def test_malformed_field_value_is_rejected(bid, device_client):
    """
    A value that can't be coerced to its field type (non-parseable
    datetime) is permanently invalid — reported `rejected`, DB-independent.
    """
    entry = {
        "outbox_id": str(uuid.uuid4()), "table_name": "customers_customer",
        "record_id": str(uuid.uuid4()), "operation": "insert",
        "payload": {
            "id": str(uuid.uuid4()), "branch_id": bid, "name": "X",
            "created_at": "not-a-real-datetime", "version": 1,
        },
        "schema_version": 1,
    }
    body = device_client.post(PUSH_URL, {"entries": [entry]}, format="json").json()
    assert body["results"][0]["status"] == "rejected"


# ---------------------------------------------------------------------------
# Per-entry isolation in a mixed batch
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_mixed_batch_applies_good_entries_despite_a_rejection(bid, device_client):
    good = Customer.objects.create(branch_id=bid, name="Good Customer")
    good_entry = entry_for(good)
    Customer.all_objects.filter(pk=good.id).delete()

    bad_entry = {
        "outbox_id": str(uuid.uuid4()), "table_name": "made_up_table",
        "record_id": str(uuid.uuid4()), "operation": "insert",
        "payload": {"id": str(uuid.uuid4()), "branch_id": bid}, "schema_version": 1,
    }

    body = device_client.post(
        PUSH_URL, {"entries": [good_entry, bad_entry]}, format="json"
    ).json()

    statuses = {r["outbox_id"]: r["status"] for r in body["results"]}
    assert statuses[good_entry["outbox_id"]] == "applied"
    assert statuses[bad_entry["outbox_id"]] == "rejected"
    assert Customer.all_objects.filter(pk=good.id).exists()


@pytest.mark.django_db
def test_push_stamps_branch_last_synced(device_branch, device_client):
    """§2.6 — a push records the branch as last-seen (HQ dashboard data)."""
    assert device_branch.last_synced_at is None
    resp = device_client.post(PUSH_URL, {"entries": []}, format="json")
    assert resp.status_code == 200
    device_branch.refresh_from_db()
    assert device_branch.last_synced_at is not None
