"""
The branch-side push loop (Phase 2 design §2.7): drain the outbox, push in
batches, record per-entry outcomes, back off when the cloud is
unreachable. One-way replication — pull is step 12.

The trigger (system cron every ~30s, or a django.tasks worker) lives
outside this function; run_push_cycle() is the whole unit of work and is
safe to call on every tick — it self-limits via the run lock and the
backoff window, and no-ops when there's nothing to send.
"""
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from .apply import EntryRejected, apply_pulled_record
from .cloud_client import TransientSyncError
from .models import OutboxEntry, SyncState

# Push cadence and backoff (§2.7): ~30s online, doubling each failure up to
# a ~15-minute ceiling.
BASE_BACKOFF_SECONDS = 30
MAX_BACKOFF_SECONDS = 900

# A run lock older than this is assumed to belong to a crashed cycle and is
# taken over — comfortably longer than a healthy cycle's HTTP timeout.
LOCK_STALE_SECONDS = 300

DEFAULT_BATCH_SIZE = 100

# Outcome codes returned by run_push_cycle for the caller/tests.
PUSHED = "pushed"
PULLED = "pulled"
NOTHING = "nothing_to_push"
SKIPPED_LOCKED = "skipped_locked"
SKIPPED_BACKOFF = "skipped_backoff"
FAILED = "failed"


def backoff_seconds(consecutive_failures):
    if consecutive_failures <= 0:
        return 0
    return min(BASE_BACKOFF_SECONDS * (2 ** (consecutive_failures - 1)), MAX_BACKOFF_SECONDS)


def _pending_qs():
    # Pending = neither synced nor terminally rejected. Oldest first, so the
    # cloud receives events roughly in the order they happened.
    return OutboxEntry.objects.filter(
        synced_at__isnull=True, rejected_at__isnull=True
    ).order_by("created_at")


def _acquire_lock(now):
    """
    Claim the run lock with a single atomic conditional UPDATE — free, or
    held-but-stale. Returns True iff this call won it. Works identically on
    SQLite and PostgreSQL (one UPDATE statement, no row-lock semantics).
    """
    SyncState.load()  # ensure the singleton row exists
    stale_before = now - timezone.timedelta(seconds=LOCK_STALE_SECONDS)
    claimed = SyncState.objects.filter(pk=1).filter(
        Q(locked_at__isnull=True) | Q(locked_at__lt=stale_before)
    ).update(locked_at=now)
    return bool(claimed)


def _release_lock():
    SyncState.objects.filter(pk=1).update(locked_at=None)


def _serialize_entry(entry):
    return {
        "outbox_id": str(entry.id),
        "table_name": entry.table_name,
        "record_id": str(entry.record_id),
        "operation": entry.operation,
        "payload": entry.payload,
        "schema_version": entry.schema_version,
        "created_at": entry.created_at.isoformat().replace("+00:00", "Z"),
    }


def run_push_cycle(*, client, batch_size=DEFAULT_BATCH_SIZE, now=None, respect_backoff=True):
    """
    Run one push cycle. `client` is a CloudClient (or any object with
    .push(entries) -> {results, server_time} raising TransientSyncError).

    Returns one of the outcome codes above. Never raises for the ordinary
    unreachable-cloud case — that's a normal offline state, recorded and
    retried, not an error.
    """
    now = now or timezone.now()
    state = SyncState.load()

    # Respect the backoff window before doing any work, so a cron tick every
    # 30s doesn't hammer a cloud that's down.
    if respect_backoff and state.consecutive_failures > 0 and state.last_attempt_at:
        due = state.last_attempt_at + timezone.timedelta(
            seconds=backoff_seconds(state.consecutive_failures)
        )
        if now < due:
            return SKIPPED_BACKOFF

    if not _acquire_lock(now):
        return SKIPPED_LOCKED

    try:
        batch = list(_pending_qs()[:batch_size])
        if not batch:
            return NOTHING

        entries = [_serialize_entry(e) for e in batch]

        try:
            response = client.push(entries)
        except TransientSyncError as exc:
            # Cloud unreachable / 5xx: leave entries pending, back off.
            SyncState.objects.filter(pk=1).update(
                last_attempt_at=now,
                consecutive_failures=state.consecutive_failures + 1,
                last_error=str(exc),
            )
            return FAILED

        results = {r["outbox_id"]: r for r in response.get("results", [])}
        synced_ids, rejected, attempted_ids = [], [], []
        for entry in batch:
            outcome = results.get(str(entry.id))
            if outcome is None:
                # Cloud silently omitted it — treat as still pending; it
                # will be re-sent next cycle.
                continue
            attempted_ids.append(entry.id)
            status = outcome.get("status")
            if status in ("applied", "duplicate"):
                synced_ids.append(entry.id)
            elif status == "rejected":
                rejected.append((entry.id, outcome.get("error", "")))

        # Count the push attempt on every entry the cloud actually ruled on.
        if attempted_ids:
            OutboxEntry.objects.filter(id__in=attempted_ids).update(
                attempted=F("attempted") + 1
            )
        if synced_ids:
            OutboxEntry.objects.filter(id__in=synced_ids).update(
                synced_at=now, last_error=None
            )
        for entry_id, reason in rejected:
            OutboxEntry.objects.filter(id=entry_id).update(
                rejected_at=now, last_error=reason
            )

        SyncState.objects.filter(pk=1).update(
            last_attempt_at=now,
            last_success_at=now,
            consecutive_failures=0,
            last_error=None,
            last_server_time=response.get("server_time") or state.last_server_time,
        )
        return PUSHED
    finally:
        _release_lock()


def run_pull_cycle(*, client, now=None, respect_backoff=True):
    """
    Pull HQ catalogue changes since the last server_time and apply them
    (Phase 2 design §2.4). Mirrors run_push_cycle: same run lock, same
    backoff, same "offline is normal, never raises" contract. Returns PULLED
    on a successful contact (even if zero records), or a skip/fail code.
    """
    now = now or timezone.now()
    state = SyncState.load()

    if respect_backoff and state.consecutive_failures > 0 and state.last_attempt_at:
        due = state.last_attempt_at + timezone.timedelta(
            seconds=backoff_seconds(state.consecutive_failures)
        )
        if now < due:
            return SKIPPED_BACKOFF

    if not _acquire_lock(now):
        return SKIPPED_LOCKED

    try:
        since = state.last_server_time
        try:
            response = client.pull(since)
        except TransientSyncError as exc:
            SyncState.objects.filter(pk=1).update(
                last_attempt_at=now,
                consecutive_failures=state.consecutive_failures + 1,
                last_error=str(exc),
            )
            return FAILED

        for record in response.get("records", []):
            # Pulls are idempotent upserts; each record is applied in its own
            # transaction so one bad row can't abort the rest. A rejected HQ
            # catalogue row shouldn't happen, but if it does it's skipped and
            # surfaced via last_error rather than stalling the whole pull.
            try:
                with transaction.atomic():
                    apply_pulled_record(record["table_name"], record["payload"])
            except EntryRejected:
                continue

        SyncState.objects.filter(pk=1).update(
            last_attempt_at=now,
            last_success_at=now,
            consecutive_failures=0,
            last_error=None,
            last_server_time=response.get("server_time") or since,
        )
        return PULLED
    finally:
        _release_lock()


def run_sync_cycle(*, client, batch_size=DEFAULT_BATCH_SIZE, now=None, respect_backoff=True):
    """
    One full cycle: push the outbox, then pull catalogue changes (§2.7). Each
    phase manages the lock and backoff itself, so if push fails the pull is
    skipped by the same backoff window rather than hammering a down cloud.
    Returns (push_outcome, pull_outcome).
    """
    now = now or timezone.now()
    push_outcome = run_push_cycle(
        client=client, batch_size=batch_size, now=now, respect_backoff=respect_backoff
    )
    pull_outcome = run_pull_cycle(client=client, now=now, respect_backoff=respect_backoff)
    return push_outcome, pull_outcome
