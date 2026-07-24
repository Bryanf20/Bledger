"""
Cloud POST /api/v1/sync/push/ — durable, idempotent receipt of branch
writes with per-entry results (Phase 2 design §2.4).
"""
import uuid

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.auth_users.models import Branch
from apps.inventory.models import Category, Product
from apps.sync.models import AppliedEntry, OutboxEntry
from apps.sync.utils import serialize_instance

PUSH_URL = reverse("sync-push")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def device_branch(db):
    return Branch.objects.create(
        business_name="Tabi Provisions",
        branch_name="Limbe Branch",
        phone="699000000",
        code="LMB",
        deployment_mode=Branch.DEPLOYMENT_CONNECTED,
        setup_complete=True,
        sync_token="dev-token",
        cloud_id=None,
    )


@pytest.fixture
def bid(device_branch):
    # Records this device pushes are stamped with its canonical identity.
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
# Applying
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_push_applies_a_new_record(bid, device_client):
    cat = Category.objects.create(branch_id=bid, name="Grains", sort_order=1)
    entry = entry_for(cat)
    Category.all_objects.filter(pk=cat.id).delete()  # not on the cloud yet
    assert not Category.all_objects.filter(pk=cat.id).exists()

    resp = device_client.post(PUSH_URL, {"entries": [entry]}, format="json")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["results"][0]["status"] == "applied"
    assert body["applied"] == 1
    assert "server_time" in body

    recreated = Category.all_objects.get(pk=cat.id)
    assert recreated.name == "Grains"
    assert AppliedEntry.objects.filter(outbox_id=entry["outbox_id"]).count() == 1


@pytest.mark.django_db
def test_push_applies_record_with_foreign_key(bid, device_client):
    cat = Category.objects.create(branch_id=bid, name="Grains", sort_order=1)
    prod = Product.objects.create(
        branch_id=bid, name="Rice 5kg", category=cat, unit="bag",
        retail_price=4500, stock_level=50,
    )
    entry = entry_for(prod)
    Product.all_objects.filter(pk=prod.id).delete()

    resp = device_client.post(PUSH_URL, {"entries": [entry]}, format="json")
    assert resp.status_code == 200, resp.content
    assert resp.json()["results"][0]["status"] == "applied"

    recreated = Product.all_objects.get(pk=prod.id)
    assert recreated.category_id == cat.id
    assert recreated.retail_price == 4500


@pytest.mark.django_db
def test_push_is_idempotent(bid, device_client):
    cat = Category.objects.create(branch_id=bid, name="Grains", sort_order=1)
    entry = entry_for(cat)
    Category.all_objects.filter(pk=cat.id).delete()

    first = device_client.post(PUSH_URL, {"entries": [entry]}, format="json")
    second = device_client.post(PUSH_URL, {"entries": [entry]}, format="json")

    assert first.json()["results"][0]["status"] == "applied"
    assert second.json()["results"][0]["status"] == "duplicate"
    assert AppliedEntry.objects.filter(outbox_id=entry["outbox_id"]).count() == 1


@pytest.mark.django_db
def test_update_preserves_branch_version_and_does_not_bump(bid, device_client):
    cat = Category.objects.create(branch_id=bid, name="Grains", sort_order=1)
    # Simulate the branch having edited this row a few times: version 5.
    payload = serialize_instance(cat)
    payload["name"] = "Cereals"
    payload["version"] = 5
    entry = {
        "outbox_id": str(uuid.uuid4()), "table_name": cat._meta.db_table,
        "record_id": str(cat.id), "operation": "update", "payload": payload,
        "schema_version": 1,
    }

    resp = device_client.post(PUSH_URL, {"entries": [entry]}, format="json")
    assert resp.json()["results"][0]["status"] == "applied"

    cat.refresh_from_db()
    assert cat.name == "Cereals"
    assert cat.version == 5  # taken from payload, not incremented to 2


@pytest.mark.django_db
def test_delete_operation_applies_soft_delete_tombstone(bid, device_client):
    cat = Category.objects.create(branch_id=bid, name="Grains", sort_order=1)
    cat.soft_delete()
    payload = serialize_instance(cat)  # deleted_at is set
    entry = {
        "outbox_id": str(uuid.uuid4()), "table_name": cat._meta.db_table,
        "record_id": str(cat.id), "operation": "delete", "payload": payload,
        "schema_version": 1,
    }
    # Wipe locally so we prove the tombstone is applied on insert.
    Category.all_objects.filter(pk=cat.id).delete()

    resp = device_client.post(PUSH_URL, {"entries": [entry]}, format="json")
    assert resp.json()["results"][0]["status"] == "applied"

    row = Category.all_objects.get(pk=cat.id)
    assert row.deleted_at is not None
    assert not Category.objects.filter(pk=cat.id).exists()  # hidden by soft-delete manager


# ---------------------------------------------------------------------------
# Rejections (permanent)
# ---------------------------------------------------------------------------


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
        "outbox_id": str(uuid.uuid4()), "table_name": "inventory_category",
        "record_id": str(uuid.uuid4()), "operation": "insert",
        "payload": {"id": str(uuid.uuid4()), "branch_id": "SOME-OTHER-BRANCH",
                    "name": "X", "sort_order": 1}, "schema_version": 1,
    }
    body = device_client.post(PUSH_URL, {"entries": [entry]}, format="json").json()
    assert body["results"][0]["status"] == "rejected"
    assert "branch" in body["results"][0]["error"].lower()


@pytest.mark.django_db
def test_malformed_field_value_is_rejected(bid, device_client):
    """
    A payload value that can't be coerced to its field type (here a
    non-parseable datetime) is permanently invalid — reported `rejected`,
    DB-independent. (Bad foreign keys are likewise rejected on the real
    PostgreSQL cloud, where FK constraints are enforced; SQLite doesn't
    enforce them, so that specific case isn't asserted here.)
    """
    entry = {
        "outbox_id": str(uuid.uuid4()), "table_name": "inventory_category",
        "record_id": str(uuid.uuid4()), "operation": "insert",
        "payload": {
            "id": str(uuid.uuid4()), "branch_id": bid, "name": "X",
            "sort_order": 1, "created_at": "not-a-real-datetime", "version": 1,
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
    good = Category.objects.create(branch_id=bid, name="Grains", sort_order=1)
    good_entry = entry_for(good)
    Category.all_objects.filter(pk=good.id).delete()

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
    # The rejection did not roll back the good entry.
    assert Category.all_objects.filter(pk=good.id).exists()
