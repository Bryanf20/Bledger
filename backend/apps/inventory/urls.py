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
#  Format-suffix URLs (.json/.api) aren't part of the API design (Part E)
# and every DefaultRouter that reaches `.urls` registers a global
# "drf_format_suffix" path converter — the second router in the process
# to do so raises ValueError. Registering it from more than
# one router raises under Django 6's stricter register_converter(), so it's
# disabled on every router in the project.
router.include_format_suffixes = False

router.register("products", views.ProductViewSet, basename="product")
router.register("categories", views.CategoryViewSet, basename="category")
router.register("price-overrides", views.BranchPriceOverrideViewSet, basename="price-override")
router.register("stock-adjustments", views.StockAdjustmentViewSet, basename="stock-adjustment")

urlpatterns = router.urls
