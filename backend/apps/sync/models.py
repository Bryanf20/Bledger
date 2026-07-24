"""
Phase 2 sync queue. OutboxEntry is deliberately not a BaseModel: it has
no FKs to application tables (design doc Part D) and isn't itself a
synced record — it's the record *of* other tables' writes.

The sync engine that drains this table (apps.sync.engine, reading
pending rows and pushing via django.tasks) is Phase 2, not built here.
This model exists now purely so the table is present from the first
Phase 1 migration and no later migration is needed to introduce it.
"""
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class OutboxEntry(models.Model):
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    OPERATION_CHOICES = [
        (INSERT, "Insert"),
        (UPDATE, "Update"),
        (DELETE, "Delete"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    table_name = models.CharField(max_length=100, db_index=True)
    record_id = models.UUIDField(db_index=True)
    operation = models.CharField(max_length=10, choices=OPERATION_CHOICES)

    # Snapshot of the record at write time — pushed to the cloud as-is,
    # not re-read from the DB later (the row may have changed again by
    # the time the sync engine runs).
    payload = models.JSONField()

    # Which version of this table's payload contract the snapshot above
    # was written against (apps.sync.registry.SYNCED_TABLES). A branch
    # that has been offline across an app upgrade will push entries
    # written by the older code; without this the cloud would have to
    # infer the contract from the payload's shape, which is guesswork
    # (Phase 2 design §8.3).
    schema_version = models.PositiveIntegerField(default=1)

    branch_id = models.CharField(max_length=64, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)

    attempted = models.PositiveIntegerField(default=0)
    last_error = models.TextField(null=True, blank=True)

    # NULL = pending. Set by the sync engine (Phase 2) after the cloud
    # confirms the push.
    synced_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.operation} {self.table_name}:{self.record_id}"


# Days a freshly minted enrolment code stays valid. Long enough that an
# owner can create the branch in the HQ dashboard and hand the code to a
# manager who sets the new device up over the following days, short enough
# that a leaked code doesn't stay usable indefinitely. Overridable via
# settings for deployments that want a tighter window.
ENROLMENT_CODE_TTL_DAYS = 7

# Human-enterable code alphabet — uppercase letters and digits with the
# visually ambiguous ones (0/O, 1/I) removed, so a manager reading a code
# off a screen and typing it on another device can't trip on them.
_ENROLMENT_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_enrolment_code(length=8):
    """A short, unambiguous, one-time enrolment code (Phase 2 design §2.3)."""
    return "".join(secrets.choice(_ENROLMENT_CODE_ALPHABET) for _ in range(length))


def default_enrolment_expiry():
    ttl_days = getattr(settings, "ENROLMENT_CODE_TTL_DAYS", ENROLMENT_CODE_TTL_DAYS)
    return timezone.now() + timedelta(days=ttl_days)


class EnrolmentCode(models.Model):
    """
    Cloud-side one-time code that lets a new device claim a branch identity
    (Phase 2 design §2.3).

    Minted by HQ when it creates a branch; consumed by that device's
    POST /api/v1/sync/enrol/. Like OutboxEntry it is NOT a BaseModel: it
    lives only on the cloud (connected.py / PostgreSQL), is never
    replicated to branches (see apps.sync.registry.NEVER_SYNCED), and is
    irrelevant on standalone installs. Deliberately minimal — enough to
    validate, expire, and single-use a code, no more.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    code = models.CharField(
        max_length=16,
        unique=True,
        db_index=True,
        default=generate_enrolment_code,
    )

    # The branch this code enrols. Created on the cloud before the code is
    # issued, so enrolment returns an identity that already exists there.
    branch = models.ForeignKey(
        "auth_users.Branch",
        on_delete=models.CASCADE,
        related_name="enrolment_codes",
    )

    expires_at = models.DateTimeField(default=default_enrolment_expiry)

    # Set the moment a device redeems the code. A non-NULL value means the
    # code is spent — enforcing the "one-time" rule (§2.3) so a leaked or
    # reused code can't enrol a second device.
    consumed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} -> {self.branch_id}"

    @property
    def is_consumed(self):
        return self.consumed_at is not None

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    def is_valid(self):
        """Redeemable exactly when it is neither spent nor expired."""
        return not self.is_consumed and not self.is_expired

    def consume(self):
        self.consumed_at = timezone.now()
        self.save(update_fields=["consumed_at"])


class AppliedEntry(models.Model):
    """
    Cloud-side idempotency ledger for pushed writes (Phase 2 design §2.4).

    A branch that pushes successfully but loses the response will re-push
    the same OutboxEntry. The unique (branch_id, outbox_id) constraint,
    checked inside the same transaction that applies the write, makes that
    re-push a no-op: the second attempt is reported `duplicate` instead of
    applying the record twice.

    Cloud-only, like OutboxEntry and EnrolmentCode — it exists solely on
    the central database and is never replicated (see
    apps.sync.registry.NEVER_SYNCED).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # The pushing branch's canonical identity (its cloud Branch row id, as
    # stamped on the records it creates) and the id of the OutboxEntry on
    # that branch. Together they uniquely identify one branch-side write.
    branch_id = models.CharField(max_length=64, db_index=True)
    outbox_id = models.UUIDField(db_index=True)

    # Denormalised for the owner-facing sync health view (§2.6) — what was
    # applied, without re-reading the target table.
    table_name = models.CharField(max_length=100)
    record_id = models.UUIDField()
    operation = models.CharField(max_length=10, choices=OutboxEntry.OPERATION_CHOICES)

    applied_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-applied_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["branch_id", "outbox_id"],
                name="uniq_applied_entry_per_branch_outbox",
            )
        ]

    def __str__(self):
        return f"{self.branch_id}:{self.outbox_id} -> {self.table_name}:{self.record_id}"
