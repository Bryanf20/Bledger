"""
Finances & cashbook views (Phase 2 design §7B).

Roles (§7B.2): recording, editing and deleting expenses/income and
managing categories is manager+ (financial bookkeeping, not a till
activity). The net-profit P&L is owner-only.

Unlike sales/purchases, a CashbookEntry IS editable and soft-deletable —
it's the owner's own bookkeeping and a mistyped amount should be fixable
(see models.py).
"""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.activity.services import log_activity
from apps.core.permissions import IsManagerOrOwner
from apps.dashboard.services import period_range, resolve_period
from apps.sync.models import OutboxEntry
from apps.sync.utils import write_outbox_entry

from .models import CashbookEntry, ExpenseCategory
from .serializers import CashbookEntrySerializer, ExpenseCategorySerializer
from .services import period_pnl


class BranchScopedQuerysetMixin:
    def get_queryset(self):
        return super().get_queryset().filter(branch_id=self.request.branch_id)


# The starter expense categories every business recognises (§7B.2).
# Seeded per branch on demand rather than in a migration — categories are
# branch-scoped (branch_id, stamped from settings.BRANCH_ID by the
# middleware), which a migration can't know, and in connected mode each
# branch is enrolled separately.
DEFAULT_EXPENSE_CATEGORIES = [
    "Rent", "Transport", "Salaries", "Utilities", "Supplies", "Losses/Damage", "Other",
]


class ExpenseCategoryViewSet(BranchScopedQuerysetMixin, viewsets.ModelViewSet):
    serializer_class = ExpenseCategorySerializer
    queryset = ExpenseCategory.objects.all()
    permission_classes = [IsAuthenticated, IsManagerOrOwner]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def perform_create(self, serializer):
        instance = serializer.save(branch_id=self.request.branch_id)
        write_outbox_entry(instance=instance, operation=OutboxEntry.INSERT)

    def perform_update(self, serializer):
        instance = serializer.save()
        write_outbox_entry(instance=instance, operation=OutboxEntry.UPDATE)

    @action(detail=False, methods=["post"], url_path="seed-defaults")
    def seed_defaults(self, request):
        """
        POST /finances/expense-categories/seed-defaults/ — creates any of
        the default categories this branch doesn't already have. Idempotent
        (skips existing names), so the frontend can call it on first visit.
        """
        existing = set(self.get_queryset().values_list("name", flat=True))
        for name in DEFAULT_EXPENSE_CATEGORIES:
            if name in existing:
                continue
            category = ExpenseCategory.objects.create(branch_id=request.branch_id, name=name)
            write_outbox_entry(instance=category, operation=OutboxEntry.INSERT)
        return Response(ExpenseCategorySerializer(self.get_queryset(), many=True).data)


class CashbookEntryViewSet(BranchScopedQuerysetMixin, viewsets.ModelViewSet):
    serializer_class = CashbookEntrySerializer
    queryset = CashbookEntry.objects.select_related("category", "recorded_by")
    permission_classes = [IsAuthenticated, IsManagerOrOwner]
    # DELETE is allowed here (soft delete) — the deliberate exception to
    # the immutable-financial-record rule for the owner's own bookkeeping.
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def perform_create(self, serializer):
        instance = serializer.save(
            branch_id=self.request.branch_id, recorded_by=self.request.user
        )
        write_outbox_entry(instance=instance, operation=OutboxEntry.INSERT)
        verb = "expense" if instance.direction == CashbookEntry.EXPENSE else "income"
        log_activity(
            self.request,
            action="expense.record",
            summary=f"Recorded {verb} of {instance.amount:,} XAF"
            + (f" ({instance.category.name})" if instance.category else ""),
            target=instance,
            metadata={"amount": instance.amount, "direction": instance.direction},
        )

    def perform_update(self, serializer):
        instance = serializer.save()
        write_outbox_entry(instance=instance, operation=OutboxEntry.UPDATE)
        log_activity(
            self.request,
            action="expense.edit",
            summary=f"Edited cashbook entry to {instance.amount:,} XAF",
            target=instance,
            metadata={"amount": instance.amount},
        )

    def perform_destroy(self, instance):
        # Soft delete + a DELETE tombstone for the cloud, same as the
        # catalogue's soft-deletes.
        instance.soft_delete()
        write_outbox_entry(instance=instance, operation=OutboxEntry.DELETE)
        log_activity(
            self.request,
            action="expense.delete",
            summary=f"Deleted cashbook entry of {instance.amount:,} XAF",
            target=instance,
            metadata={"amount": instance.amount},
        )


class PnLView(APIView):
    """
    GET /api/v1/finances/pnl/?period=today|week|month — the period
    profit-and-loss (§7B.3): gross margin − expenses + income = net
    profit, plus the expense-by-category breakdown.

    Manager+ (§7C.4): every other dashboard financial (gross margin,
    COGS, stock valuation) is already manager-visible, so net profit —
    which is just gross margin minus expenses — is too, rather than being
    the one owner-only number. Relaxed from the original owner-only in
    step 8f so the dashboard can show one honest bottom line.
    """

    permission_classes = [IsManagerOrOwner]

    def get(self, request):
        period = resolve_period(request.query_params.get("period"))
        start, end = period_range(period)
        data = period_pnl(request.branch_id, start, end)
        data["period"] = period
        return Response(data)
