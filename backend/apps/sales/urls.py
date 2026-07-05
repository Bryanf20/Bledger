from rest_framework.routers import DefaultRouter

from .views import HeldSaleViewSet, SaleViewSet

router = DefaultRouter()
router.include_format_suffixes = False

router.register("sales", SaleViewSet, basename="sale")
router.register("held-sales", HeldSaleViewSet, basename="heldsale")

urlpatterns = router.urls
