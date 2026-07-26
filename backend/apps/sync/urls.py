"""
Sync endpoints (Phase 2, Stage 3). Mounted at /api/v1/sync/ from the root
urlconf. Step 9 ships the two enrolment endpoints; push/pull/status arrive
in later steps.
"""
from django.urls import path

from .views import (
    BranchProvisionView,
    EnrolView,
    HealthView,
    PullView,
    PushView,
    StatusView,
)

urlpatterns = [
    path("enrol/", EnrolView.as_view(), name="sync-enrol"),
    path("branches/", BranchProvisionView.as_view(), name="sync-branch-provision"),
    path("push/", PushView.as_view(), name="sync-push"),
    path("pull/", PullView.as_view(), name="sync-pull"),
    path("status/", StatusView.as_view(), name="sync-status"),
    path("health/", HealthView.as_view(), name="sync-health"),
]
