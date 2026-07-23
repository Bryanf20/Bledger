from rest_framework.routers import DefaultRouter

from .views import ActivityLogViewSet

router = DefaultRouter()
# See sales/urls.py — disable format suffixes (Django 6 converter gotcha).
router.include_format_suffixes = False

router.register("activity", ActivityLogViewSet, basename="activity-log")

urlpatterns = router.urls
