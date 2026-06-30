"""
core has no business-logic endpoints of its own. The single health-check
view here exists only so this skeleton is runnable and verifiable before
any other app is built.
"""
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    return Response(
        {
            "status": "ok",
            "deployment_mode": settings.DEPLOYMENT_MODE,
            "sync_enabled": getattr(settings, "SYNC_ENABLED", False),
            "branch_id": settings.BRANCH_ID,
        }
    )
