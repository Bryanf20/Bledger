from rest_framework.exceptions import APIException
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.core.permissions import IsManagerOrOwner
from apps.inventory.models import Product

from .reports.csv_report import csv_response
from .reports.pdf_report import PdfReportNotReady, generate_pdf_report
from .services import period_range, resolve_period
from .views import _branch_sales


class ServiceUnavailable(APIException):
    status_code = 503
    default_detail = "This export format isn't available yet."
    default_code = "service_unavailable"


class BaseReportView(APIView):
    """Shared ?export=csv|pdf switch for all three /reports/ endpoints.
    Manager/owner only (design doc E.5) — same financial-data gating as
    the dashboard aggregate views, stricter than stock-alerts.

    Named `export`, not `format`: DRF's DefaultContentNegotiation
    treats `?format=` as reserved for content-type negotiation —
    `filter_renderers()` raises Http404 before the view even runs if
    the value doesn't match a registered renderer's `.format` (e.g.
    'pdf' isn't a renderer this APIView has), which is exactly the case
    this endpoint needs to handle itself."""

    permission_classes = [IsAuthenticated, IsManagerOrOwner]
    filename = "report.csv"
    header = []

    def get(self, request):
        export_format = request.query_params.get("export", "csv").lower()
        rows = self.get_rows(request)
        if export_format == "pdf":
            try:
                return generate_pdf_report(self.filename, self.header, rows)
            except PdfReportNotReady as exc:
                raise ServiceUnavailable(str(exc))
        return csv_response(self.filename, self.header, rows)

    def get_rows(self, request):
        raise NotImplementedError


class SalesReportView(BaseReportView):
    """GET /api/v1/reports/sales/?period=today|week|month&export=csv|pdf"""

    filename = "sales_report.csv"
    header = ["Reference", "Date", "Cashier", "Payment method", "Total"]

    def get_rows(self, request):
        period = resolve_period(request.query_params.get("period"))
        start, end = period_range(period)
        sales = _branch_sales(request, start, end).select_related("cashier").order_by("created_at")
        return [
            [s.reference, s.created_at.isoformat(), s.cashier.name, s.payment_method, s.total_amount]
            for s in sales
        ]


class ProductsReportView(BaseReportView):
    """GET /api/v1/reports/products/?export=csv|pdf — full catalogue, not
    period-filtered (a catalogue snapshot, not a sales-activity report)."""

    filename = "products_report.csv"
    header = ["Product", "Category", "Retail price", "Bulk price", "Stock level"]

    def get_rows(self, request):
        products = Product.objects.filter(branch_id=request.branch_id, is_active=True).select_related("category")
        return [
            [p.name, p.category.name if p.category else "", p.retail_price, p.bulk_price or "", p.stock_level]
            for p in products
        ]


class StockReportView(BaseReportView):
    """GET /api/v1/reports/stock/?export=csv|pdf — stock-value / low-stock
    report per the feasibility doc (9.1). Not period-filtered — a
    point-in-time stock snapshot."""

    filename = "stock_report.csv"
    header = ["Product", "Stock level", "Low stock threshold", "Status"]

    def get_rows(self, request):
        products = Product.objects.filter(branch_id=request.branch_id, is_active=True)
        return [[p.name, p.stock_level, p.low_stock_threshold, p.stock_status] for p in products]
