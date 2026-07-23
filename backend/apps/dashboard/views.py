from django.db.models import Count, F, IntegerField, Q, Sum, Value
from django.db.models.functions import Coalesce, TruncDay, TruncHour
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsCashierOrAbove, IsManagerOrOwner
from apps.core.utils.xaf import round_xaf
from apps.inventory.models import Product
from apps.sales.models import Sale, SaleLineItem

from .serializers import (
    DashboardSummarySerializer,
    PaymentBreakdownSerializer,
    SalesChartPointSerializer,
    StockAlertSerializer,
    TopProductSerializer,
)
from .services import period_range, previous_period_range, resolve_period


def _branch_sales(request, start, end):
    """Completed sales for the caller's branch within [start, end).
    Voided sales are excluded from every dashboard figure — they never
    happened as far as revenue/reporting is concerned (contrast the
    sales app itself, which keeps the voided Sale row for audit).
    request.branch_id is stamped by DeploymentContextMiddleware from
    settings.BRANCH_ID (apps.core.middleware) — same as every other
    app's BranchScopedQuerysetMixin."""
    return Sale.objects.filter(
        branch_id=request.branch_id,
        status=Sale.COMPLETED,
        created_at__gte=start,
        created_at__lt=end,
    )


class SalesSummaryView(APIView):
    """GET /api/v1/dashboard/summary/?period=today|week|month

    KPI strip: revenue, transaction count, average sale, top product —
    each with a period-over-period delta (design doc B.5)."""

    permission_classes = [IsManagerOrOwner]

    def get(self, request):
        period = resolve_period(request.query_params.get("period"))
        start, end = period_range(period)
        prev_start, prev_end = previous_period_range(period, start, end)

        sales = _branch_sales(request, start, end)
        prev_sales = _branch_sales(request, prev_start, prev_end)

        agg = sales.aggregate(
            revenue=Coalesce(Sum("total_amount"), Value(0, output_field=IntegerField())),
            transaction_count=Count("id"),
        )
        prev_agg = prev_sales.aggregate(
            revenue=Coalesce(Sum("total_amount"), Value(0, output_field=IntegerField())),
            transaction_count=Count("id"),
        )

        revenue = agg["revenue"]
        transaction_count = agg["transaction_count"]
        average_sale = round_xaf(revenue / transaction_count) if transaction_count else 0

        prev_revenue = prev_agg["revenue"]
        revenue_change_pct = (
            float((revenue - prev_revenue) / prev_revenue * 100) if prev_revenue else None
        )

        top_line = (
            SaleLineItem.objects.filter(sale__in=sales)
            .values("product__name")
            .annotate(units=Sum("quantity"))
            .order_by("-units")
            .first()
        )

        data = {
            "period": period,
            "revenue": revenue,
            "revenue_change_pct": revenue_change_pct,
            "transaction_count": transaction_count,
            "transaction_count_change": transaction_count - prev_agg["transaction_count"],
            "average_sale": average_sale,
            "top_product_name": top_line["product__name"] if top_line else None,
        }
        return Response(DashboardSummarySerializer(data).data)


class TopProductsView(APIView):
    """GET /api/v1/dashboard/top-products/?period=today|week|month&limit=10

    Not paginated — this is a small ranked list (design doc shows top 3
    on the dashboard card), not a browsable collection, so DRF's
    pagination classes don't apply here and the annotate()-plus-pagination
    ordering gotcha (see suppliers.SupplierViewSet.get_queryset()) doesn't
    come up. `limit` is capped so a caller can't force an unbounded
    aggregate scan."""

    permission_classes = [IsManagerOrOwner]

    def get(self, request):
        period = resolve_period(request.query_params.get("period"))
        start, end = period_range(period)
        limit = min(int(request.query_params.get("limit", 10)), 50)

        sales = _branch_sales(request, start, end)
        rows = (
            SaleLineItem.objects.filter(sale__in=sales)
            .values("product_id", "product__name")
            .annotate(units_sold=Sum("quantity"), revenue=Sum("line_total"))
            .order_by("-revenue")[:limit]
        )

        data = [
            {
                "rank": i + 1,
                "product_id": row["product_id"],
                "product_name": row["product__name"],
                "units_sold": row["units_sold"],
                "revenue": row["revenue"],
            }
            for i, row in enumerate(rows)
        ]
        return Response(TopProductSerializer(data, many=True).data)


class PaymentBreakdownView(APIView):
    """GET /api/v1/dashboard/payment-breakdown/?period=today|week|month

    Cash vs MTN MoMo vs Orange Money split (design doc B.5 — "first-class
    widget, not buried in a report")."""

    permission_classes = [IsManagerOrOwner]

    def get(self, request):
        period = resolve_period(request.query_params.get("period"))
        start, end = period_range(period)

        rows = (
            _branch_sales(request, start, end)
            .values("payment_method")
            .annotate(revenue=Sum("total_amount"), transaction_count=Count("id"))
            .order_by("-revenue")
        )
        return Response(PaymentBreakdownSerializer(rows, many=True).data)


class VarianceSummaryView(APIView):
    """GET /api/v1/dashboard/variance-summary/?period=today|week|month

    Negotiated-pricing outcomes (Phase 2 design §3.4): total surplus
    collected (haggled above catalogue), total discount given (below),
    the net, and a per-cashier breakdown — the fraud-detection surface,
    so an owner can see who consistently discounts. Manager+ only.

    Amounts are line-level: per-unit `variance` × quantity, over
    completed (non-voided) sales in the period. Brokered lines are
    included — a negotiated price on a sourced item is still surplus or
    discount on the selling price."""

    permission_classes = [IsManagerOrOwner]

    def get(self, request):
        period = resolve_period(request.query_params.get("period"))
        start, end = period_range(period)
        lines = SaleLineItem.objects.filter(sale__in=_branch_sales(request, start, end))

        line_amount = F("variance") * F("quantity")
        totals = lines.aggregate(
            surplus=Coalesce(
                Sum(line_amount, filter=Q(variance__gt=0)), Value(0, output_field=IntegerField())
            ),
            # Discount comes out negative (variance < 0); flip to a
            # positive "revenue foregone" figure below.
            discount=Coalesce(
                Sum(line_amount, filter=Q(variance__lt=0)), Value(0, output_field=IntegerField())
            ),
        )
        total_surplus = totals["surplus"]
        total_discount = -totals["discount"]

        per_cashier = [
            {
                "cashier_id": row["sale__cashier"],
                "cashier_name": row["sale__cashier__name"],
                "surplus": row["surplus"],
                "discount": -row["discount"],
                "net": row["surplus"] + row["discount"],
            }
            for row in (
                lines.exclude(variance=0)
                .values("sale__cashier", "sale__cashier__name")
                .annotate(
                    surplus=Coalesce(
                        Sum(line_amount, filter=Q(variance__gt=0)),
                        Value(0, output_field=IntegerField()),
                    ),
                    discount=Coalesce(
                        Sum(line_amount, filter=Q(variance__lt=0)),
                        Value(0, output_field=IntegerField()),
                    ),
                )
                .order_by("sale__cashier__name")
            )
        ]

        return Response(
            {
                "period": period,
                "total_surplus": total_surplus,
                "total_discount": total_discount,
                "net_variance": total_surplus - total_discount,
                "per_cashier": per_cashier,
            }
        )


class MarginSummaryView(APIView):
    """GET /api/v1/dashboard/margin-summary/?period=today|week|month

    Gross margin for the period (Phase 2 design §7A.6): revenue minus
    cost of goods sold, over completed (non-voided) sale lines whose COGS
    is known. Lines with unit_cost_at_sale = 0 (cost never set) are
    excluded from BOTH revenue and COGS so the margin isn't inflated to a
    false 100%; their revenue is reported separately as `uncosted_revenue`
    for context. Manager+ only — cost is financial data."""

    permission_classes = [IsManagerOrOwner]

    def get(self, request):
        period = resolve_period(request.query_params.get("period"))
        start, end = period_range(period)
        lines = SaleLineItem.objects.filter(sale__in=_branch_sales(request, start, end))

        costed = lines.filter(unit_cost_at_sale__gt=0)
        agg = costed.aggregate(
            revenue=Coalesce(Sum("line_total"), Value(0, output_field=IntegerField())),
            cogs=Coalesce(
                Sum(F("unit_cost_at_sale") * F("quantity")),
                Value(0, output_field=IntegerField()),
            ),
        )
        revenue = agg["revenue"]
        cogs = agg["cogs"]
        gross_margin = revenue - cogs
        margin_pct = round((gross_margin / revenue) * 100, 1) if revenue else None

        total_revenue = lines.aggregate(
            r=Coalesce(Sum("line_total"), Value(0, output_field=IntegerField()))
        )["r"]

        return Response(
            {
                "period": period,
                "revenue": revenue,          # revenue from cost-known lines only
                "cogs": cogs,
                "gross_margin": gross_margin,
                "margin_pct": margin_pct,
                "total_revenue": total_revenue,               # all completed lines
                "uncosted_revenue": total_revenue - revenue,  # excluded from margin
            }
        )


class StockValuationView(APIView):
    """GET /api/v1/dashboard/stock-valuation/

    The money currently sitting on the shelves (§7A.6): Σ(stock_level ×
    average_cost) over active products whose cost is known — often the
    single largest asset in these businesses and previously invisible.
    Products with no cost basis are counted separately, not valued at 0.
    Not period-scoped (a live snapshot). Manager+ only."""

    permission_classes = [IsManagerOrOwner]

    def get(self, request):
        products = Product.objects.filter(branch_id=request.branch_id, is_active=True)
        costed = products.filter(cost_is_set=True)
        value = costed.aggregate(
            v=Coalesce(
                Sum(F("stock_level") * F("average_cost")),
                Value(0, output_field=IntegerField()),
            )
        )["v"]
        return Response(
            {
                "stock_value": value,
                "costed_products": costed.count(),
                "cost_unknown_products": products.filter(cost_is_set=False).count(),
            }
        )


class LowMarginView(APIView):
    """GET /api/v1/dashboard/low-margin/

    Products whose margin has thinned to below the business's
    margin-alert threshold, or which are selling at or below cost
    (§7A.6 — the quiet killer of small-retail margins). Only products
    with a known cost are considered; sorted worst-first. Manager+."""

    permission_classes = [IsManagerOrOwner]

    def get(self, request):
        from apps.auth_users.models import BusinessSettings

        threshold = BusinessSettings.load().margin_alert_pct
        products = Product.objects.filter(
            branch_id=request.branch_id, is_active=True, cost_is_set=True
        )
        rows = []
        for p in products:
            if p.retail_price <= 0:
                continue
            margin = p.retail_price - p.average_cost
            margin_pct = round((margin / p.retail_price) * 100, 1)
            if margin_pct < threshold:
                rows.append(
                    {
                        "product_id": str(p.id),
                        "name": p.name,
                        "retail_price": p.retail_price,
                        "average_cost": p.average_cost,
                        "margin": margin,
                        "margin_pct": margin_pct,
                        "at_or_below_cost": margin <= 0,
                    }
                )
        rows.sort(key=lambda r: r["margin_pct"])
        return Response({"threshold_pct": threshold, "products": rows})


class SalesChartView(APIView):
    """GET /api/v1/dashboard/sales-chart/?period=today|week|month

    'today' buckets by hour (the B.5 "Sales by hour" bar chart); 'week'
    and 'month' bucket by day. Returns plain {label, revenue} points —
    per design doc B.5 the frontend renders these as CSS bars, no chart
    library, so there's no need to shape this around a specific charting
    lib's expected format."""

    permission_classes = [IsManagerOrOwner]

    def get(self, request):
        period = resolve_period(request.query_params.get("period"))
        start, end = period_range(period)
        sales = _branch_sales(request, start, end)

        trunc = TruncHour("created_at") if period == "today" else TruncDay("created_at")
        rows = (
            sales.annotate(bucket=trunc)
            .values("bucket")
            .annotate(revenue=Sum("total_amount"))
            .order_by("bucket")
        )

        label_fmt = "%I%p" if period == "today" else "%d %b"
        data = [
            {"label": row["bucket"].strftime(label_fmt).lstrip("0").lower(), "revenue": row["revenue"]}
            for row in rows
        ]
        return Response(SalesChartPointSerializer(data, many=True).data)


class StockAlertView(APIView):
    """GET /api/v1/dashboard/stock-alerts/

    Available to all roles, including cashier — design doc E.5 calls
    this out explicitly as an exception to the manager+ financial
    gating every other dashboard endpoint uses. Not paginated, not
    period-filtered (a live snapshot, not a browsable catalogue — that's
    what /products/ is for)."""

    permission_classes = [IsCashierOrAbove]

    def get(self, request):
        products = (
            Product.objects.filter(branch_id=request.branch_id, is_active=True)
            .filter(stock_level__lte=F("low_stock_threshold"))
            .order_by("stock_level")
        )
        data = [
            {
                "product_id": p.id,
                "product_name": p.name,
                "stock_level": p.stock_level,
                "low_stock_threshold": p.low_stock_threshold,
                "status": p.stock_status,
            }
            for p in products
        ]
        return Response(StockAlertSerializer(data, many=True).data)
