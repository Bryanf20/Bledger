from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import CashbookEntryViewSet, ExpenseCategoryViewSet, PnLView

router = DefaultRouter()
# See sales/urls.py — disable format suffixes (Django 6 converter gotcha).
router.include_format_suffixes = False

router.register("finances/expense-categories", ExpenseCategoryViewSet, basename="expense-category")
router.register("finances/cashbook", CashbookEntryViewSet, basename="cashbook-entry")

urlpatterns = router.urls + [
    path("finances/pnl/", PnLView.as_view(), name="finances-pnl"),
]
