"""
Branch-side push loop (Phase 2 design §2.7): drain the outbox, mark
outcomes, back off when the cloud is unreachable, never double-push.
Exercises engine.run_push_cycle against a fake CloudClient — no network.
"""
import uuid

import pytest
from django.utils import timezone

from apps.inventory.models import Category
from apps.sync.cloud_client import TransientSyncError
from apps.sync.engine import (
    FAILED,
    NOTHING,
    PUSHED,
    SKIPPED_BACKOFF,
    SKIPPED_LOCKED,
    backoff_seconds,
    run_push_cycle,
)
from apps.sync.models import OutboxEntry, SyncState
from apps.sync.utils import write_outbox_entry

BID = "HQ"


class FakeCloud:
    """A CloudClient stand-in. Records what it was sent; replies per script."""

    def __init__(self, reply=None, raise_transient=False):
        self.reply = reply
        self.raise_transient = raise_transient
        self.calls = []

    def push(self, entries):
        self.calls.append(entries)
        if self.raise_transient:
            raise TransientSyncError("cloud down")
        if self.reply is not None:
            return self.reply
        # Default: accept everything.
        return {
            "results": [{"outbox_id": e["outbox_id"], "status": "applied"} for e in entries],
            "server_time": "2026-07-24T00:00:00Z",
        }


def _make_entry(name="Grains"):
    cat = Category.objects.create(branch_id=BID, name=name, sort_order=1)
    return write_outbox_entry(instance=cat, operation=OutboxEntry.INSERT)


# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_empty_outbox_is_a_noop():
    cloud = FakeCloud()
    assert run_push_cycle(client=cloud) == NOTHING
    assert cloud.calls == []


@pytest.mark.django_db
def test_applied_entries_are_marked_synced():
    e = _make_entry()
    assert run_push_cycle(client=FakeCloud()) == PUSHED

    e.refresh_from_db()
    assert e.synced_at is not None
    assert e.rejected_at is None
    assert e.attempted == 1

    state = SyncState.load()
    assert state.consecutive_failures == 0
    assert state.last_success_at is not None
    assert state.last_server_time == "2026-07-24T00:00:00Z"
    assert state.locked_at is None  # lock released


@pytest.mark.django_db
def test_duplicate_counts_as_synced():
    e = _make_entry()
    reply = {"results": [{"outbox_id": str(e.id), "status": "duplicate"}],
             "server_time": "2026-07-24T00:00:00Z"}
    assert run_push_cycle(client=FakeCloud(reply=reply)) == PUSHED
    e.refresh_from_db()
    assert e.synced_at is not None


@pytest.mark.django_db
def test_rejected_entry_is_marked_and_not_retried():
    e = _make_entry()
    reply = {
        "results": [{"outbox_id": str(e.id), "status": "rejected", "error": "bad table"}],
        "server_time": "2026-07-24T00:00:00Z",
    }
    cloud = FakeCloud(reply=reply)
    assert run_push_cycle(client=cloud) == PUSHED

    e.refresh_from_db()
    assert e.rejected_at is not None
    assert e.synced_at is None
    assert e.last_error == "bad table"

    # A second cycle must NOT resend it — it's terminal.
    cloud2 = FakeCloud()
    assert run_push_cycle(client=cloud2) == NOTHING
    assert cloud2.calls == []


@pytest.mark.django_db
def test_only_pending_entries_are_pushed():
    done = _make_entry("Already")
    OutboxEntry.objects.filter(pk=done.pk).update(synced_at=timezone.now())
    pending = _make_entry("Fresh")

    cloud = FakeCloud()
    run_push_cycle(client=cloud)

    sent_ids = {en["outbox_id"] for en in cloud.calls[0]}
    assert str(pending.id) in sent_ids
    assert str(done.id) not in sent_ids


@pytest.mark.django_db
def test_transient_failure_backs_off_and_leaves_entries_pending():
    e = _make_entry()
    now = timezone.now()
    assert run_push_cycle(client=FakeCloud(raise_transient=True), now=now) == FAILED

    e.refresh_from_db()
    assert e.synced_at is None and e.rejected_at is None  # still pending

    state = SyncState.load()
    assert state.consecutive_failures == 1
    assert state.last_error == "cloud down"
    assert state.locked_at is None  # released even on failure


@pytest.mark.django_db
def test_backoff_window_skips_until_due():
    _make_entry()
    t0 = timezone.now()
    # First attempt fails -> 1 failure, backoff = 30s.
    run_push_cycle(client=FakeCloud(raise_transient=True), now=t0)

    # 10s later: still inside the 30s window -> skipped, cloud not called.
    cloud = FakeCloud()
    soon = t0 + timezone.timedelta(seconds=10)
    assert run_push_cycle(client=cloud, now=soon) == SKIPPED_BACKOFF
    assert cloud.calls == []

    # 31s later: window elapsed -> pushes.
    later = t0 + timezone.timedelta(seconds=31)
    assert run_push_cycle(client=FakeCloud(), now=later) == PUSHED


@pytest.mark.django_db
def test_held_lock_skips_the_cycle():
    _make_entry()
    # Simulate another run holding a fresh lock.
    SyncState.load()
    SyncState.objects.filter(pk=1).update(locked_at=timezone.now())

    cloud = FakeCloud()
    assert run_push_cycle(client=cloud, now=timezone.now()) == SKIPPED_LOCKED
    assert cloud.calls == []


@pytest.mark.django_db
def test_batch_size_limits_entries_per_cycle():
    for i in range(3):
        _make_entry(f"Item {i}")
    cloud = FakeCloud()
    run_push_cycle(client=cloud, batch_size=2)
    assert len(cloud.calls[0]) == 2  # only two sent this cycle


def test_backoff_curve_is_exponential_with_ceiling():
    assert backoff_seconds(0) == 0
    assert backoff_seconds(1) == 30
    assert backoff_seconds(2) == 60
    assert backoff_seconds(3) == 120
    assert backoff_seconds(100) == 900  # capped at 15 min
