"""
GET /api/v1/sync/health/ — owner-only sync health with rejected-with-reasons
(Phase 2 design §2.6).
"""
import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.inventory.models import Category
from apps.sync.models import OutboxEntry, SyncState
from apps.sync.utils import write_outbox_entry

from .conftest import client_for

HEALTH_URL = reverse("sync-health")


def _rejected_entry(reason="bad table"):
    cat = Category.objects.create(branch_id="HQ", name="Grains", sort_order=1)
    entry = write_outbox_entry(instance=cat, operation=OutboxEntry.INSERT)
    OutboxEntry.objects.filter(pk=entry.pk).update(
        rejected_at=timezone.now(), last_error=reason
    )
    return entry


@pytest.mark.django_db
def test_health_requires_owner(manager_user):
    assert client_for(manager_user).get(HEALTH_URL).status_code == 403


@pytest.mark.django_db
def test_health_requires_authentication():
    assert APIClient().get(HEALTH_URL).status_code in (401, 403)


@pytest.mark.django_db
def test_health_lists_rejected_with_reasons(owner_user):
    _rejected_entry("inventory_category is HQ-owned catalogue")

    body = client_for(owner_user).get(HEALTH_URL).json()
    assert body["rejected_count"] == 1
    assert len(body["rejected"]) == 1
    row = body["rejected"][0]
    assert row["table_name"] == "inventory_category"
    assert "catalogue" in row["last_error"]
    assert row["rejected_at"] is not None


@pytest.mark.django_db
def test_health_reports_pending_and_state(owner_user):
    cat = Category.objects.create(branch_id="HQ", name="Pending", sort_order=1)
    write_outbox_entry(instance=cat, operation=OutboxEntry.INSERT)  # pending

    state = SyncState.load()
    state.consecutive_failures = 2
    state.last_error = "cloud down"
    state.save()

    with override_settings(SYNC_ENABLED=True):
        body = client_for(owner_user).get(HEALTH_URL).json()

    assert body["sync_enabled"] is True
    assert body["pending"] == 1
    assert body["consecutive_failures"] == 2
    assert body["last_error"] == "cloud down"
