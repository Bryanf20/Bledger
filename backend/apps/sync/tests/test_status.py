"""
GET /api/v1/sync/status/ — local connectivity read for the frontend
sync indicator (Phase 2 design §2.6).
"""
import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.inventory.models import Category
from apps.sync.models import OutboxEntry, SyncState
from apps.sync.utils import write_outbox_entry

from .conftest import client_for

STATUS_URL = reverse("sync-status")


@pytest.mark.django_db
def test_status_requires_authentication():
    from rest_framework.test import APIClient

    assert APIClient().get(STATUS_URL).status_code in (401, 403)


@pytest.mark.django_db
def test_status_reports_pending_and_synced(owner_user):
    cat = Category.objects.create(branch_id="HQ", name="Grains", sort_order=1)
    write_outbox_entry(instance=cat, operation=OutboxEntry.INSERT)

    with override_settings(SYNC_ENABLED=True):
        body = client_for(owner_user).get(STATUS_URL).json()

    assert body["sync_enabled"] is True
    assert body["pending"] == 1
    assert body["rejected"] == 0
    assert body["connectivity"] == "syncing"  # pending > 0, no failures


@pytest.mark.django_db
def test_status_synced_when_nothing_pending(owner_user):
    with override_settings(SYNC_ENABLED=True):
        body = client_for(owner_user).get(STATUS_URL).json()
    assert body["connectivity"] == "synced"


@pytest.mark.django_db
def test_status_offline_when_failing(owner_user):
    state = SyncState.load()
    state.consecutive_failures = 3
    state.last_error = "cloud down"
    state.save()

    with override_settings(SYNC_ENABLED=True):
        body = client_for(owner_user).get(STATUS_URL).json()

    assert body["connectivity"] == "offline"
    assert body["consecutive_failures"] == 3
    assert body["last_error"] == "cloud down"


@pytest.mark.django_db
def test_status_disabled_in_standalone(owner_user):
    with override_settings(SYNC_ENABLED=False):
        body = client_for(owner_user).get(STATUS_URL).json()
    assert body["connectivity"] == "disabled"


@pytest.mark.django_db
def test_status_counts_rejected(owner_user):
    cat = Category.objects.create(branch_id="HQ", name="Grains", sort_order=1)
    entry = write_outbox_entry(instance=cat, operation=OutboxEntry.INSERT)
    OutboxEntry.objects.filter(pk=entry.pk).update(rejected_at=timezone.now())

    with override_settings(SYNC_ENABLED=True):
        body = client_for(owner_user).get(STATUS_URL).json()

    assert body["pending"] == 0  # rejected no longer counts as pending
    assert body["rejected"] == 1
