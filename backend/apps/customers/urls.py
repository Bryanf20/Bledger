from rest_framework.routers import DefaultRouter

from .views import CustomerViewSet

router = DefaultRouter()
# See sales/urls.py — a second router registering format suffixes trips
# Django 6's stricter converter registration, so disable them.
router.include_format_suffixes = False

router.register("customers", CustomerViewSet, basename="customer")

urlpatterns = router.urls
