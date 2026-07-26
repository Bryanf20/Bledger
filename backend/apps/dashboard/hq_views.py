"""
HQ multi-branch dashboard (Phase 2 design §2.4 "aggregation is the HQ
dashboard's job, reading cloud Postgres directly" / §2.6 per-branch
last-seen). Owner-only, cross-branch — the counterpart to the branch-scoped
views in views.py, which filter to request.branch_id.

On the cloud (connected.py / PostgreSQL) every branch's records coexist, so
these aggregate across all of them. On a single branch device the same
endpoints degenerate to that one branch. This is the owner-facing payoff of
the whole sync workstream.
"""
from django.conf import settings
from django.db.models import Count, IntegerField, Sum, Value
from django.db.models.functions import Coalesce
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.auth_users.models import Branch
from apps.core.permissions import IsOwner
from apps.sales.models import Sale

from .services import period_range, resolve_period


def _branch_lookup():
    """
    Map a record's stamped branch_id -> its Branch row.

    Enrolled branches stamp branch_id = str(their cloud Branch.id), so those
    match directly. HQ's own records instead carry settings.BRANCH_ID (the
    cloud's DeploymentContextMiddleware falls back to it because HQ's row has
    no cloud_id) — so the HQ/only branch is additionally keyed under that
    value. This reconciles the two identity conventions (open decision §10.2)
    without a schema change.
    """
    lookup = {}
    for b in Branch.objects.all():
        lookup[str(b.id)] = b
    hq = Branch.objects.filter(is_hq=True).first() or Branch.objects.first()
    if hq is not None:
        lookup.setdefault(settings.BRANCH_ID, hq)
    return lookup


class HQSummaryView(APIView):
    """
    GET /api/v1/hq/summary/?period=today|week|month — cross-branch revenue
    and transaction totals with a per-branch breakdown and each branch's
    last-seen time. Owner-only.
    """

    permission_classes = [IsOwner]

    def get(self, request):
        period = resolve_period(request.query_params.get("period"))
        start, end = period_range(period)

        sales = Sale.objects.filter(
            status=Sale.COMPLETED, created_at__gte=start, created_at__lt=end
        )
        per_branch = (
            sales.values("branch_id")
            .annotate(
                revenue=Coalesce(Sum("total_amount"), Value(0, output_field=IntegerField())),
                transaction_count=Count("id"),
            )
            .order_by("-revenue")
        )

        lookup = _branch_lookup()
        rows = []
        seen_branch_pks = set()
        total_revenue = 0
        total_transactions = 0

        def row_for(branch, branch_id, revenue, txn):
            return {
                "branch_id": branch_id,
                "branch_name": (branch.branch_name or branch.business_name) if branch else branch_id,
                "code": branch.code if branch else None,
                "is_hq": branch.is_hq if branch else False,
                "is_active": branch.is_active if branch else True,
                "last_synced_at": branch.last_synced_at if branch else None,
                "revenue": revenue,
                "transaction_count": txn,
            }

        for r in per_branch:
            branch = lookup.get(r["branch_id"])
            rows.append(row_for(branch, r["branch_id"], r["revenue"], r["transaction_count"]))
            if branch is not None:
                seen_branch_pks.add(branch.pk)
            total_revenue += r["revenue"]
            total_transactions += r["transaction_count"]

        # Include branches with no sales this period, so the owner sees every
        # branch (an idle or newly-enrolled one is exactly what they'd want to
        # spot), each with its own last-seen.
        for branch in Branch.objects.all():
            if branch.pk not in seen_branch_pks:
                rows.append(row_for(branch, str(branch.id), 0, 0))

        rows.sort(key=lambda x: (-x["revenue"], x["branch_name"] or ""))

        return Response(
            {
                "period": period,
                "branch_count": Branch.objects.count(),
                "total_revenue": total_revenue,
                "total_transactions": total_transactions,
                "branches": rows,
            }
        )
