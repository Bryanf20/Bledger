from django.urls import path

from .reports_views import ProductsReportView, SalesReportView, StockReportView
from .views import (
    PaymentBreakdownView,
    SalesChartView,
    SalesSummaryView,
    StockAlertView,
    TopProductsView,
)

# No ViewSets/DefaultRouter in this app — every endpoint is a function-style
# aggregate or report view (see project instructions "On the horizon"), so
# the `router.include_format_suffixes = False` gotcha doesn't apply here.
# If a ViewSet is ever added to this app, apply it immediately on
# instantiation, same as inventory/sales/suppliers.

urlpatterns = [
    path("dashboard/summary/", SalesSummaryView.as_view(), name="dashboard-summary"),
    path("dashboard/top-products/", TopProductsView.as_view(), name="dashboard-top-products"),
    path("dashboard/payment-breakdown/", PaymentBreakdownView.as_view(), name="dashboard-payment-breakdown"),
    path("dashboard/sales-chart/", SalesChartView.as_view(), name="dashboard-sales-chart"),
    path("dashboard/stock-alerts/", StockAlertView.as_view(), name="dashboard-stock-alerts"),
    path("reports/sales/", SalesReportView.as_view(), name="reports-sales"),
    path("reports/products/", ProductsReportView.as_view(), name="reports-products"),
    path("reports/stock/", StockReportView.as_view(), name="reports-stock"),
]
