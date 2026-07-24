"""
Serializers for the Phase 2 enrolment endpoints (Stage 3, step 9 —
§2.3). Deliberately thin: they validate and normalise input, while the
consume-and-issue logic lives in the views where it can hold a row lock.
"""
from rest_framework import serializers


class EnrolRequestSerializer(serializers.Serializer):
    """
    Body of POST /api/v1/sync/enrol/. A device presents the one-time code
    it was given; `device_name` is optional and purely for the owner's
    later benefit when reading a branch's history.
    """

    code = serializers.CharField(max_length=16)
    device_name = serializers.CharField(
        max_length=120, required=False, allow_blank=True, default=""
    )

    def validate_code(self, value):
        # Codes are minted from an uppercase, unambiguous alphabet; accept
        # a manager's lowercase / whitespace-padded typing and normalise.
        normalised = value.strip().upper()
        if not normalised:
            raise serializers.ValidationError("An enrolment code is required.")
        return normalised


class BranchProvisionSerializer(serializers.Serializer):
    """
    Body of POST /api/v1/sync/branches/ — HQ (owner) creates a branch on
    the cloud and gets back a one-time enrolment code. `code` is the short
    reference discriminator (§8.1); if omitted it is derived from the
    branch name. Full HQ branch-management UI is step 14 — this is the
    minimal seam that makes enrolment reachable and testable.
    """

    branch_name = serializers.CharField(max_length=200)
    code = serializers.CharField(max_length=8, required=False, allow_blank=True, default="")
    is_hq = serializers.BooleanField(required=False, default=False)
    address = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")

    def validate_code(self, value):
        from apps.auth_users.models import Branch

        normalised = value.strip().upper()
        if normalised and Branch.objects.filter(code=normalised).exists():
            raise serializers.ValidationError(
                f"Branch code {normalised!r} is already taken."
            )
        return normalised


class PushEntrySerializer(serializers.Serializer):
    """
    One outbox entry as a branch sends it (Phase 2 design §2.4). Mirrors the
    OutboxEntry row shape the device drained: the ids let the cloud dedupe
    and report per-entry, the payload is the full snapshot to apply.
    """

    OPERATION_CHOICES = ["insert", "update", "delete"]

    outbox_id = serializers.UUIDField()
    table_name = serializers.CharField(max_length=100)
    record_id = serializers.UUIDField()
    operation = serializers.ChoiceField(choices=OPERATION_CHOICES)
    payload = serializers.DictField()
    schema_version = serializers.IntegerField(min_value=1, required=False, default=1)
    # The branch's own created_at, kept for the owner's audit view only —
    # the cloud never orders by a device clock (§2.4).
    created_at = serializers.DateTimeField(required=False)


class PushRequestSerializer(serializers.Serializer):
    """Body of POST /api/v1/sync/push/ — a bounded batch of entries."""

    # ~100 per push in normal operation (§2.7); cap generously so a backlog
    # flush after a long offline spell still goes in a few requests, but a
    # single request can't be unboundedly large.
    entries = PushEntrySerializer(many=True, allow_empty=True, max_length=500)
