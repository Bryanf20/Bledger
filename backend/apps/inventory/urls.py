"""
GET/POST /products/, PATCH /products/{id}/
GET/POST /categories/
GET/POST /stock-adjustments/
GET/POST /price-overrides/

Mounted at /api/v1/ (no extra prefix) in bledger/urls.py, matching API
reference E.2.
"""
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("products", views.ProductViewSet, basename="product")
router.register("categories", views.CategoryViewSet, basename="category")
router.register("price-overrides", views.BranchPriceOverrideViewSet, basename="price-override")
router.register("stock-adjustments", views.StockAdjustmentViewSet, basename="stock-adjustment")

urlpatterns = router.urls
