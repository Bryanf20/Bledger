"""
Single write path into the outbox, so any app can add one line to its
own atomic transaction rather than reimplementing the outbox row shape.

NOT wired retroactively into apps.inventory's StockAdjustment /
BranchPriceOverride writes — treat that as a separate, deliberate
"backfill the outbox" task rather than something to fix incidentally.
"""
from .models import OutboxEntry


def write_outbox_entry(*, instance, operation, branch_id=None):
    """
    Call inside the same transaction as the write to `instance`.
    `instance` must have a UUID `id`. `branch_id` defaults to
    `instance.branch_id` (every BaseModel has one); pass explicitly
    for models that don't.
    """
    if branch_id is None:
        branch_id = getattr(instance, "branch_id", None)

    OutboxEntry.objects.create(
        table_name=instance._meta.db_table,
        record_id=instance.id,
        operation=operation,
        payload=_snapshot(instance),
        branch_id=branch_id,
    )


def _snapshot(instance):
    """
    Minimal JSON-safe field snapshot — deliberately dumb (str() on
    anything non-primitive). The Phase 2 sync engine defines the real
    serialization contract per table; this just guarantees the outbox
    row exists and round-trips a usable payload.
    """
    data = {}
    for field in instance._meta.fields:
        value = getattr(instance, field.name)
        if value is None or isinstance(value, (str, int, float, bool)):
            data[field.name] = value
        else:
            data[field.name] = str(value)
    return data
