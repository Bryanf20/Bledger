"""
Phase 2 sync queue. OutboxEntry is deliberately not a BaseModel: it has
no FKs to application tables (design doc Part D) and isn't itself a
synced record — it's the record *of* other tables' writes.

The sync engine that drains this table (apps.sync.engine, reading
pending rows and pushing via django.tasks) is Phase 2, not built here.
This model exists now purely so the table is present from the first
Phase 1 migration and no later migration is needed to introduce it.
"""
import uuid

from django.db import models


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
    