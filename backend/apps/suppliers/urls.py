"""
GET/POST /suppliers/, PATCH /suppliers/{id}/
GET/POST /purchases/

Mounted at /api/v1/ (no extra prefix) in bledger/urls.py, matching API
reference E.4 — same pattern as apps.inventory.urls and apps.sales.urls.
"""
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
# See apps.inventory.urls / apps.sales.urls — DefaultRouter.urls
# registers a process-wide "drf_format_suffix" converter; only one
# router in the whole urlconf may do so.
router.include_format_suffixes = False

router.register("suppliers", views.SupplierViewSet, basename="supplier")
router.register("purchases", views.PurchaseViewSet, basename="purchase")
router.register("purchase-orders", views.PurchaseOrderViewSet, basename="purchase-order")

urlpatterns = router.urls
