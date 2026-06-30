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
        request.branch_id = settings.BRANCH_ID

        response = self.get_response(request)

        response["X-Deployment-Mode"] = settings.DEPLOYMENT_MODE
        response["X-Sync-Enabled"] = str(getattr(settings, "SYNC_ENABLED", False)).lower()
        return response
