"""
Enrolment endpoints (Phase 2, Stage 3, step 9 — §2.3). These run on the
*cloud* side of the sync relationship:

  POST /api/v1/sync/branches/   HQ owner provisions a branch + gets a code
  POST /api/v1/sync/enrol/      a new device redeems the code, receiving
                                its canonical branch_id and sync token

The branch *device* side (setup-wizard "Connect to head office", persisting
the returned identity into its local Branch row) is frontend work in a later
step; the push/pull protocol these identities authenticate is step 10.
"""
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.auth_users.models import Branch, derive_branch_code, generate_sync_token
from apps.core.permissions import IsCashierOrAbove, IsOwner
from apps.inventory.models import HQ_BRANCH_ID, Category, Product

from .apply import APPLIED, DUPLICATE, REJECTED, EntryRejected, apply_entry
from .authentication import DeviceSyncTokenAuthentication
from .models import EnrolmentCode, OutboxEntry, SyncState
from .permissions import IsEnrolledDevice
from .serializers import (
    BranchProvisionSerializer,
    EnrolRequestSerializer,
    PushRequestSerializer,
)
from .utils import serialize_instance


class BranchProvisionView(APIView):
    """
    POST /api/v1/sync/branches/ — owner-only. Creates a branch on the cloud
    and returns a one-time enrolment code for it. Minimal by design; the
    full HQ branch-management screen is step 14.
    """

    permission_classes = [IsAuthenticated, IsOwner]

    def post(self, request):
        serializer = BranchProvisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # New branches share the requesting owner's business name; only the
        # branch_name and code distinguish them.
        requester_branch = getattr(request.user, "branch", None)
        business_name = getattr(requester_branch, "business_name", "") or data["branch_name"]

        code = data["code"] or derive_branch_code(
            data["branch_name"],
            business_name,
            taken=Branch.objects.values_list("code", flat=True),
        )

        with transaction.atomic():
            branch = Branch.objects.create(
                business_name=business_name,
                branch_name=data["branch_name"],
                address=data["address"],
                phone=data["phone"],
                code=code,
                is_hq=data["is_hq"],
                deployment_mode=Branch.DEPLOYMENT_CONNECTED,
                # Setup completes on the device when it enrols, not here.
                setup_complete=False,
                is_active=True,
            )
            enrolment = EnrolmentCode.objects.create(branch=branch)

        return Response(
            {
                "branch_id": str(branch.id),
                "branch_name": branch.branch_name,
                "code": branch.code,
                "is_hq": branch.is_hq,
                "enrolment_code": enrolment.code,
                "expires_at": enrolment.expires_at,
            },
            status=status.HTTP_201_CREATED,
        )


class EnrolView(APIView):
    """
    POST /api/v1/sync/enrol/ — a new device redeems its one-time code. No
    authentication: the device has neither a user session nor a sync token
    yet; the code itself is the credential (§2.3).
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = EnrolRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data["code"]

        with transaction.atomic():
            # Lock the code row so two devices racing on the same code can't
            # both pass the validity check and enrol.
            try:
                enrolment = (
                    EnrolmentCode.objects.select_for_update()
                    .select_related("branch")
                    .get(code=code)
                )
            except EnrolmentCode.DoesNotExist:
                return Response(
                    {"detail": "Invalid or unknown enrolment code."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if enrolment.is_consumed:
                return Response(
                    {"detail": "This enrolment code has already been used."},
                    status=status.HTTP_409_CONFLICT,
                )
            if enrolment.is_expired:
                return Response(
                    {"detail": "This enrolment code has expired."},
                    status=status.HTTP_410_GONE,
                )

            branch = enrolment.branch
            if not branch.is_active:
                return Response(
                    {"detail": "This branch has been deactivated."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Issue the device sync token if the branch doesn't have one yet.
            # Re-provisioned branches keep their existing token.
            if not branch.sync_token:
                branch.sync_token = generate_sync_token()
                branch.save(update_fields=["sync_token", "updated_at"])

            enrolment.consume()

        return Response(
            {
                # The canonical branch_id the device stamps on its records.
                "branch_id": str(branch.id),
                "sync_token": branch.sync_token,
                "code": branch.code,
                "business_name": branch.business_name,
                "branch_name": branch.branch_name,
                "is_hq": branch.is_hq,
                "deployment_mode": branch.deployment_mode,
            },
            status=status.HTTP_200_OK,
        )


class PushView(APIView):
    """
    POST /api/v1/sync/push/ — a branch device pushes a batch of drained
    outbox entries; the cloud applies each and reports a per-entry outcome
    so one poison row can't block the queue (Phase 2 design §2.4).

    Authenticated by the device sync token, not a user — sync runs with
    nobody logged in.
    """

    authentication_classes = [DeviceSyncTokenAuthentication]
    permission_classes = [IsEnrolledDevice]

    def post(self, request):
        serializer = PushRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entries = serializer.validated_data["entries"]

        # The authenticated branch's canonical identity — what its records
        # are stamped with, and what AppliedEntry keys dedupe against.
        branch_id = str(request.auth.id)
        # Record this branch as last-seen now (§2.6 per-branch last-seen,
        # surfaced by the HQ dashboard). A bare timestamp write, no version.
        Branch.objects.filter(pk=request.auth.pk).update(last_synced_at=timezone.now())

        results = []
        for entry in entries:
            outbox_id = entry["outbox_id"]
            try:
                status_str = apply_entry(branch_id=branch_id, entry=entry)
                results.append({"outbox_id": str(outbox_id), "status": status_str})
            except EntryRejected as exc:
                results.append(
                    {
                        "outbox_id": str(outbox_id),
                        "status": REJECTED,
                        "error": exc.reason,
                    }
                )

        # server_time is the cloud clock the branch stores and later passes
        # as ?since= on pull (§2.4) — field clocks are never trusted.
        return Response(
            {
                "results": results,
                "applied": sum(r["status"] == APPLIED for r in results),
                "duplicate": sum(r["status"] == DUPLICATE for r in results),
                "rejected": sum(r["status"] == REJECTED for r in results),
                "server_time": timezone.now().isoformat().replace("+00:00", "Z"),
            }
        )


class StatusView(APIView):
    """
    GET /api/v1/sync/status/ — local, user-authenticated connectivity read
    for the frontend's sync indicator (Phase 2 design §2.6). Any staff role
    may see it; sync health is not privileged information and offline is a
    normal working state, never an error.
    """

    permission_classes = [IsCashierOrAbove]

    def get(self, request):
        sync_enabled = bool(getattr(settings, "SYNC_ENABLED", False))
        pending = OutboxEntry.objects.filter(
            synced_at__isnull=True, rejected_at__isnull=True
        ).count()
        rejected = OutboxEntry.objects.filter(rejected_at__isnull=False).count()

        state = SyncState.objects.filter(pk=1).first()
        failures = state.consecutive_failures if state else 0
        last_success_at = state.last_success_at if state else None
        last_error = state.last_error if state else None

        # Four connectivity states (§2.6). "disabled" is the standalone
        # case where there is no cloud at all.
        if not sync_enabled:
            connectivity = "disabled"
        elif failures > 0:
            connectivity = "offline"
        elif pending > 0:
            connectivity = "syncing"
        else:
            connectivity = "synced"

        return Response(
            {
                "sync_enabled": sync_enabled,
                "connectivity": connectivity,
                "pending": pending,
                "rejected": rejected,
                "consecutive_failures": failures,
                "last_success_at": last_success_at,
                "last_error": last_error,
            }
        )


class PullView(APIView):
    """
    GET /api/v1/sync/pull/?since=<server_timestamp> — the cloud serves this
    branch the changes it needs (Phase 2 design §2.4): the HQ product
    catalogue (Category, Product) and tombstones for soft-deleted catalogue
    rows. A branch never pulls another branch's sales or stock — aggregation
    is the HQ dashboard's job (step 14).

    Catalogue is the one shared layer (§2.1); users and business config are a
    later pull increment. `since` is the cloud clock this branch last saw
    (returned as server_time); absent means a full catalogue snapshot. Device
    clocks are never used (§2.4).
    """

    authentication_classes = [DeviceSyncTokenAuthentication]
    permission_classes = [IsEnrolledDevice]

    # Catalogue is emitted Category-before-Product so a branch applying the
    # batch in order never hits a Product whose Category isn't there yet.
    CATALOGUE_MODELS = (Category, Product)

    def get(self, request):
        # Record last-seen for the HQ dashboard (§2.6), same as push.
        Branch.objects.filter(pk=request.auth.pk).update(last_synced_at=timezone.now())
        since_raw = request.query_params.get("since")
        since = parse_datetime(since_raw.replace("Z", "+00:00")) if since_raw else None

        records = []
        for model in self.CATALOGUE_MODELS:
            # all_objects, not objects: soft-deleted rows must be included so
            # their tombstones propagate (§2.5).
            qs = model.all_objects.filter(branch_id=HQ_BRANCH_ID)
            if since is not None:
                qs = qs.filter(updated_at__gt=since)
            for row in qs.order_by("updated_at"):
                records.append(
                    {
                        "table_name": model._meta.db_table,
                        "operation": "delete" if row.deleted_at else "update",
                        "payload": serialize_instance(row),
                    }
                )

        return Response(
            {
                "records": records,
                "count": len(records),
                "server_time": timezone.now().isoformat().replace("+00:00", "Z"),
            }
        )


class HealthView(APIView):
    """
    GET /api/v1/sync/health/ — owner-only sync health (Phase 2 design §2.6).
    Rejected entries are silent data loss unless someone can see them, so
    this lists them with their reasons alongside the pending backlog and the
    last-contact state. Per-branch last-seen (the HQ cross-branch view) is
    step 14; this is the device's own health.
    """

    permission_classes = [IsOwner]

    # Cap the rejected list so a pathological backlog can't return an
    # unbounded response; the count above it is always exact.
    REJECTED_LIMIT = 200

    def get(self, request):
        rejected_qs = OutboxEntry.objects.filter(rejected_at__isnull=False).order_by(
            "-rejected_at"
        )
        rejected = [
            {
                "id": str(e.id),
                "table_name": e.table_name,
                "record_id": str(e.record_id),
                "operation": e.operation,
                "attempted": e.attempted,
                "last_error": e.last_error,
                "created_at": e.created_at,
                "rejected_at": e.rejected_at,
            }
            for e in rejected_qs[: self.REJECTED_LIMIT]
        ]
        pending = OutboxEntry.objects.filter(
            synced_at__isnull=True, rejected_at__isnull=True
        ).count()

        state = SyncState.objects.filter(pk=1).first()
        return Response(
            {
                "sync_enabled": bool(getattr(settings, "SYNC_ENABLED", False)),
                "pending": pending,
                "rejected_count": rejected_qs.count(),
                "rejected": rejected,
                "last_success_at": state.last_success_at if state else None,
                "last_attempt_at": state.last_attempt_at if state else None,
                "consecutive_failures": state.consecutive_failures if state else 0,
                "last_error": state.last_error if state else None,
            }
        )
