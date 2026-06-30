"""
BaseModel — the abstract base every Phase 1 model inherits from, except
Branch, BledgerUser, and OutboxEntry (see design doc Part D).

Columns mirror the "required columns on every synced table" spec in
Bledger_Feasibility_Design_v0.3.docx Section 8.2:

    id          UUID (text)        globally unique, no collisions across
                                    branches creating records offline
    branch_id   text                originating branch, used for filtering
    created_at  ISO timestamp       immutable, used in audit trails
    updated_at  ISO timestamp       updated on every write
    deleted_at  ISO timestamp/null  soft delete only, never hard-deleted
    synced_at   ISO timestamp/null  NULL = pending sync (Phase 2)
    version     integer             optimistic concurrency control
"""
import uuid

from django.db import models


class SoftDeleteManager(models.Manager):
    """Default manager — excludes soft-deleted rows."""

    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Identifies the originating branch. In standalone mode this is a
    # single fixed value (settings.BRANCH_ID); in connected mode it
    # varies per branch device. Indexed because almost every query
    # filters by it.
    branch_id = models.CharField(max_length=64, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Soft delete — never hard-deleted, so tombstones can propagate to
    # branches via sync (Phase 2).
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    # NULL = pending sync. Set by the sync engine after cloud confirms
    # the write. Always NULL in standalone mode (sync disabled).
    synced_at = models.DateTimeField(null=True, blank=True)

    # Incremented on each update — optimistic concurrency control on
    # catalogue records during cloud sync (Phase 2).
    version = models.PositiveIntegerField(default=1)

    objects = SoftDeleteManager()
    all_objects = models.Manager()  # bypasses the soft-delete filter

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def soft_delete(self):
        from django.utils import timezone

        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at", "updated_at"])

    def save(self, *args, **kwargs):
        if not self._state.adding:
            self.version = (self.version or 0) + 1
        super().save(*args, **kwargs)
