"""
Activity log read API (step 8c). Read-only — the log is written only
through `services.log_activity` at the point events happen, never through
the API.

Visibility tiers (§7C): a manager sees the key operational events
(`is_major=True`); an owner sees everything, including owner-only detail
rows. Cashiers have no access — finances/audit is above the till.
"""
from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.core.permissions import IsManagerOrOwner

from .models import ActivityLog
from .serializers import ActivityLogSerializer


class ActivityLogViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = ActivityLogSerializer
    permission_classes = [IsAuthenticated, IsManagerOrOwner]

    def get_queryset(self):
        qs = ActivityLog.objects.filter(branch_id=self.request.branch_id).select_related("actor")

        # Owners see everything; managers see only the major events.
        if getattr(self.request.user, "role", None) != "owner":
            qs = qs.filter(is_major=True)

        # Optional lightweight filters for the screen's controls.
        action = self.request.query_params.get("action")
        if action:
            qs = qs.filter(action=action)
        actor = self.request.query_params.get("actor")
        if actor:
            qs = qs.filter(actor_id=actor)
        return qs
