"""
Two-way sync: GET /api/v1/sync/pull/ (cloud serves HQ catalogue + tombstones)
and engine.run_pull_cycle (branch applies them). Phase 2 design §2.4, §2.5.
"""
import uuid

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.auth_users.models import Branch
from apps.inventory.models import HQ_BRANCH_ID, Category, Product
from apps.sync.cloud_client import TransientSyncError
from apps.sync.engine import FAILED, PULLED, SKIPPED_LOCKED, run_pull_cycle, run_sync_cycle
from apps.sync.models import SyncState

PULL_URL = reverse("sync-pull")


@pytest.fixture
def device_branch(db):
    return Branch.objects.create(
        business_name="Tabi Provisions", branch_name="Limbe Branch",
        phone="699000000", code="LMB",
        deployment_mode=Branch.DEPLOYMENT_CONNECTED, setup_complete=True,
        sync_token="dev-token",
    )


@pytest.fixture
def device_client(device_branch):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION="SyncToken dev-token")
    return c


def _hq_category(name="Grains"):
    return Category.objects.create(branch_id=HQ_BRANCH_ID, name=name, sort_order=1)


def _hq_product(cat, name="Rice 5kg"):
    return Product.objects.create(
        branch_id=HQ_BRANCH_ID, name=name, category=cat, unit="bag",
        retail_price=4500, stock_level=0,
    )


# ---------------------------------------------------------------------------
# Cloud endpoint
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_pull_requires_a_device_token():
    assert APIClient().get(PULL_URL).status_code in (401, 403)


@pytest.mark.django_db
def test_pull_returns_hq_catalogue(device_client):
    cat = _hq_category()
    _hq_product(cat)

    body = device_client.get(PULL_URL).json()
    tables = {r["table_name"] for r in body["records"]}
    assert "inventory_category" in tables
    assert "inventory_product" in tables
    assert body["count"] == 2
    assert body["server_time"].endswith("Z")
    # Category is emitted before Product (FK-safe apply order).
    idx = [r["table_name"] for r in body["records"]]
    assert idx.index("inventory_category") < idx.index("inventory_product")


@pytest.mark.django_db
def test_pull_excludes_other_branches_records(device_client):
    _hq_category("HQ Grains")
    # A branch-local customer is not catalogue and must never be pulled.
    from apps.customers.models import Customer
    Customer.objects.create(branch_id="SOMEBRANCH", name="Local Only")

    body = device_client.get(PULL_URL).json()
    tables = {r["table_name"] for r in body["records"]}
    assert tables == {"inventory_category"}


@pytest.mark.django_db
def test_pull_since_filters_to_changes_after(device_client):
    _hq_category("Old")
    cutoff = timezone.now()
    later = _hq_category("New")

    body = device_client.get(PULL_URL, {"since": cutoff.isoformat().replace("+00:00", "Z")}).json()
    names = {r["payload"]["name"] for r in body["records"]}
    assert "New" in names
    assert "Old" not in names


@pytest.mark.django_db
def test_pull_includes_tombstones(device_client):
    cat = _hq_category("Discontinued")
    cat.soft_delete()

    body = device_client.get(PULL_URL).json()
    rec = next(r for r in body["records"] if r["table_name"] == "inventory_category")
    assert rec["operation"] == "delete"
    assert rec["payload"]["deleted_at"] is not None


# ---------------------------------------------------------------------------
# Branch apply cycle
# ---------------------------------------------------------------------------


class FakeCloud:
    def __init__(self, response=None, raise_transient=False):
        self.response = response
        self.raise_transient = raise_transient
        self.since_seen = "unset"

    def pull(self, since=None):
        self.since_seen = since
        if self.raise_transient:
            raise TransientSyncError("cloud down")
        return self.response


@pytest.mark.django_db
def test_run_pull_cycle_applies_catalogue_and_advances_since():
    cat_id = str(uuid.uuid4())
    prod_id = str(uuid.uuid4())
    response = {
        "records": [
            {"table_name": "inventory_category", "operation": "update",
             "payload": {"id": cat_id, "branch_id": HQ_BRANCH_ID, "name": "Grains",
                         "sort_order": 1, "version": 1}},
            {"table_name": "inventory_product", "operation": "update",
             "payload": {"id": prod_id, "branch_id": HQ_BRANCH_ID, "name": "Rice",
                         "category_id": cat_id, "unit": "bag", "retail_price": 4500,
                         "stock_level": 0, "version": 1}},
        ],
        "server_time": "2026-07-24T12:00:00Z",
    }
    assert run_pull_cycle(client=FakeCloud(response=response)) == PULLED

    assert Category.all_objects.filter(pk=cat_id).exists()
    prod = Product.all_objects.get(pk=prod_id)
    assert prod.category_id == uuid.UUID(cat_id)
    assert prod.retail_price == 4500

    state = SyncState.load()
    assert state.last_server_time == "2026-07-24T12:00:00Z"
    assert state.consecutive_failures == 0
    assert state.locked_at is None


@pytest.mark.django_db
def test_run_pull_cycle_applies_tombstone():
    cat = _hq_category("ToDelete")
    from apps.sync.utils import serialize_instance
    cat.soft_delete()
    payload = serialize_instance(cat)
    Category.all_objects.filter(pk=cat.id).delete()

    response = {"records": [{"table_name": "inventory_category",
                             "operation": "delete", "payload": payload}],
                "server_time": "2026-07-24T12:00:00Z"}
    assert run_pull_cycle(client=FakeCloud(response=response)) == PULLED

    row = Category.all_objects.get(pk=cat.id)
    assert row.deleted_at is not None
    assert not Category.objects.filter(pk=cat.id).exists()


@pytest.mark.django_db
def test_run_pull_cycle_sends_last_server_time_as_since():
    state = SyncState.load()
    state.last_server_time = "2026-07-01T00:00:00Z"
    state.save()
    cloud = FakeCloud(response={"records": [], "server_time": "2026-07-24T12:00:00Z"})
    run_pull_cycle(client=cloud)
    assert cloud.since_seen == "2026-07-01T00:00:00Z"


@pytest.mark.django_db
def test_run_pull_cycle_backs_off_on_transient():
    now = timezone.now()
    assert run_pull_cycle(client=FakeCloud(raise_transient=True), now=now) == FAILED
    state = SyncState.load()
    assert state.consecutive_failures == 1
    assert state.locked_at is None


@pytest.mark.django_db
def test_run_pull_cycle_respects_lock():
    SyncState.load()
    SyncState.objects.filter(pk=1).update(locked_at=timezone.now())
    cloud = FakeCloud(response={"records": [], "server_time": "x"})
    assert run_pull_cycle(client=cloud, now=timezone.now()) == SKIPPED_LOCKED
    assert cloud.since_seen == "unset"


@pytest.mark.django_db
def test_run_sync_cycle_runs_push_then_pull():
    class BothCloud:
        def push(self, entries):
            return {"results": [], "server_time": "2026-07-24T12:00:00Z"}

        def pull(self, since=None):
            return {"records": [], "server_time": "2026-07-24T12:00:00Z"}

    push_outcome, pull_outcome = run_sync_cycle(client=BothCloud())
    assert pull_outcome == PULLED  # push had nothing, pull contacted cloud


# ---------------------------------------------------------------------------
# Users + business config (cloud -> branch, §2.4 / §7.2)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_pull_includes_branch_users(device_client, device_branch):
    from apps.auth_users.models import BledgerUser

    BledgerUser.objects.create_user(
        username="cashier_lmb", branch=device_branch, role="cashier", pin="4321",
        name="Cashier LMB",
    )
    body = device_client.get(PULL_URL).json()
    user_recs = [r for r in body["records"] if r["table_name"] == "auth_users_bledgeruser"]
    assert len(user_recs) == 1
    assert user_recs[0]["payload"]["username"] == "cashier_lmb"
    # branch_id is stamped with the cloud Branch id (FK the device resolves).
    assert user_recs[0]["payload"]["branch_id"] == str(device_branch.id)


@pytest.mark.django_db
def test_pull_excludes_other_branches_users(device_client, device_branch):
    from apps.auth_users.models import BledgerUser

    other = Branch.objects.create(
        business_name="X", branch_name="Other", phone="6", code="OTH",
        deployment_mode=Branch.DEPLOYMENT_CONNECTED, setup_complete=True,
    )
    BledgerUser.objects.create_user(username="ours", branch=device_branch, role="cashier", pin="1111", name="Ours")
    BledgerUser.objects.create_user(username="theirs", branch=other, role="cashier", pin="2222", name="Theirs")

    body = device_client.get(PULL_URL).json()
    usernames = {r["payload"]["username"] for r in body["records"] if r["table_name"] == "auth_users_bledgeruser"}
    assert usernames == {"ours"}


@pytest.mark.django_db
def test_pull_includes_business_settings(device_client):
    from apps.auth_users.models import BusinessSettings

    BusinessSettings.load()  # ensure the singleton exists
    body = device_client.get(PULL_URL).json()
    settings_recs = [r for r in body["records"] if r["table_name"] == "auth_users_businesssettings"]
    assert len(settings_recs) == 1
    assert settings_recs[0]["payload"]["id"] == 1


@pytest.mark.django_db
def test_run_pull_cycle_applies_a_user_with_branch_fk():
    from apps.auth_users.models import BledgerUser, Branch as B

    # The device's local Branch uses the cloud branch id as its pk (enrolment
    # aligns them), so a pulled user's branch_id resolves.
    cloud_bid = "33333333-3333-3333-3333-333333333333"
    B.objects.create(
        id=cloud_bid, cloud_id=cloud_bid, business_name="Tabi", branch_name="LMB",
        code="LMB", deployment_mode=B.DEPLOYMENT_CONNECTED, setup_complete=True,
    )
    uid = "44444444-4444-4444-4444-444444444444"
    response = {
        "records": [{
            "table_name": "auth_users_bledgeruser", "operation": "update",
            "payload": {
                "id": uid, "branch_id": cloud_bid, "username": "pulled_user",
                "name": "Pulled User", "role": "cashier", "pin_hash": "",
                "password": "!", "is_active": True, "is_staff": False,
                "is_superuser": False, "last_login": None,
            },
        }],
        "server_time": "2026-07-24T12:00:00Z",
    }
    assert run_pull_cycle(client=FakeCloud(response=response)) == PULLED
    u = BledgerUser.objects.get(pk=uid)
    assert u.username == "pulled_user"
    assert u.branch_id == B.objects.get(pk=cloud_bid).id


@pytest.mark.django_db
def test_run_pull_cycle_applies_business_settings():
    from apps.auth_users.models import BusinessSettings

    response = {
        "records": [{
            "table_name": "auth_users_businesssettings", "operation": "update",
            "payload": {"id": 1, "default_credit_limit": 25000},
        }],
        "server_time": "2026-07-24T12:00:00Z",
    }
    assert run_pull_cycle(client=FakeCloud(response=response)) == PULLED
    assert BusinessSettings.objects.get(pk=1).default_credit_limit == 25000
