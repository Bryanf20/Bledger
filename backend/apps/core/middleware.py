"""
Stamps deployment context onto every request/response so views and
templates (e.g. the receipt printer) don't need to import settings
directly, and so the frontend can read sync/branch status from response
headers without an extra API round-trip.
"""
from django.conf import settings


class DeploymentContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.deployment_mode = settings.DEPLOYMENT_MODE
        request.branch_id = self._resolve_branch_id()

        response = self.get_response(request)

        response["X-Deployment-Mode"] = settings.DEPLOYMENT_MODE
        response["X-Sync-Enabled"] = str(getattr(settings, "SYNC_ENABLED", False)).lower()
        return response

    def _resolve_branch_id(self):
        """
        Which branch_id to stamp on this request's writes.

        Phase 1 / standalone (unchanged): the fixed env constant
        settings.BRANCH_ID. This is the invariant the rest of the codebase
        was built on — request.branch_id is a single fixed value.

        Phase 2 branch device (§2.3): once a device has enrolled, the cloud
        assigned it a canonical identity that lives on its local Branch row
        (Branch.cloud_id). From then on records must carry THAT id, not the
        env default, so the cloud attributes them to the right branch. We
        therefore prefer the enrolled row's cloud_id when sync is on, and
        fall back to settings.BRANCH_ID whenever it isn't set — which keeps
        standalone installs (cloud_id always NULL) and the cloud server
        itself (identifies branches by their own row id, so no local
        cloud_id) behaving exactly as before.
        """
        if getattr(settings, "SYNC_ENABLED", False):
            enrolled = self._enrolled_cloud_id()
            if enrolled:
                return enrolled
        return settings.BRANCH_ID

    @staticmethod
    def _enrolled_cloud_id():
        # Imported lazily: middleware is constructed during app loading,
        # before the model registry is ready. Guarded so a request served
        # before migrations run (fresh DB, table absent) can't 500 here —
        # it simply falls back to settings.BRANCH_ID.
        from django.db import DatabaseError

        from apps.auth_users.models import Branch

        try:
            return (
                Branch.objects.filter(cloud_id__isnull=False, is_active=True)
                .values_list("cloud_id", flat=True)
                .first()
            )
        except DatabaseError:
            return None
