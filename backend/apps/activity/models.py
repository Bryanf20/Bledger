"""
Activity log (Phase 2 design §7C / step 8c).

A unified, append-only trail of the major things that happen in a branch
— logins, staff changes, price changes, stock adjustments, expenses, sale
voids, credit-limit changes, settings edits — so an owner can answer
"who did what, when" from one screen. Sales are deliberately NOT logged
here: they already have their own history and receipts, and logging every
sale would drown the signal.

Two visibility tiers, driven by `is_major`:
  - managers see only `is_major=True` rows (the key operational events),
  - owners see everything, including fine-grained catalogue edits.

Append-only: rows are created and never updated or deleted — same
audit-trail principle as StockAdjustment / ProductPriceHistory. Branch-
owned, so it syncs branch → cloud like the rest.
"""
from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class ActivityLog(BaseModel):
    # Dotted action key, e.g. "sale.void", "staff.create", "price.change".
    action = models.CharField(max_length=40)
    # Human-readable one-liner shown in the log, e.g.
    # "Voided sale BLD-BUE-2026-0007 (12,500 XAF)".
    summary = models.CharField(max_length=255)
    # True = a key event every manager should see; False = owner-only
    # detail (routine catalogue edits and the like).
    is_major = models.BooleanField(default=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_events",
    )
    # Loose reference to the affected object (no cross-app FK — the log
    # must survive the target being hard-deleted, and points at objects in
    # many apps). target_type is the model name, target_id its pk string.
    target_type = models.CharField(max_length=40, blank=True, default="")
    target_id = models.CharField(max_length=64, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta(BaseModel.Meta):
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["branch_id", "-created_at"]),
            models.Index(fields=["branch_id", "is_major", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.action}: {self.summary}"
