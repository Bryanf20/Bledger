"""
`log_activity` — the single write path for the activity log (step 8c).

Call it from a view/serializer at the point a major thing happens. It
resolves the actor and branch from the request, writes the append-only
row, and enqueues its outbox entry — so callers stay one line:

    log_activity(request, action="sale.void", summary=f"Voided {sale.reference}", target=sale)

Keep the summary human-readable and self-contained (it's shown verbatim);
put anything structured a screen might filter on in `metadata`.
"""
from apps.sync.models import OutboxEntry
from apps.sync.utils import write_outbox_entry

from .models import ActivityLog

# The action keys that are surfaced to managers (is_major default True).
# This module-level list doubles as the canonical catalogue of what the
# log tracks — see PHASE2_DESIGN §7C.
MAJOR_ACTIONS = {
    "auth.login",
    "sale.void",
    "expense.record",
    "expense.edit",
    "expense.delete",
    "staff.create",
    "staff.update",
    "staff.deactivate",
    "staff.reset_pin",
    "stock.adjust",
    "stock.loss_booked",
    "credit.limit_change",
    "settings.update",
}


def log_activity(
    request=None,
    *,
    action,
    summary,
    is_major=None,
    actor=None,
    branch_id=None,
    target=None,
    target_type="",
    target_id="",
    metadata=None,
):
    if request is not None:
        if branch_id is None:
            branch_id = getattr(request, "branch_id", None)
        if actor is None:
            actor = getattr(request, "user", None)

    # A DRF AnonymousUser (failed/absent auth) has no pk — store null.
    if actor is not None and not getattr(actor, "pk", None):
        actor = None

    if target is not None:
        target_type = target._meta.model_name
        target_id = str(target.pk)

    if is_major is None:
        is_major = action in MAJOR_ACTIONS

    entry = ActivityLog.objects.create(
        branch_id=branch_id,
        action=action,
        summary=summary,
        is_major=is_major,
        actor=actor,
        target_type=target_type,
        target_id=str(target_id),
        metadata=metadata or {},
    )
    write_outbox_entry(instance=entry, operation=OutboxEntry.INSERT, branch_id=branch_id)
    return entry
