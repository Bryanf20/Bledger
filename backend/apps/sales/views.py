from django.http import HttpResponse
from django.utils.dateparse import parse_date
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import ROLE_CASHIER, IsCashierOrAbove, IsManagerOrOwner
from apps.printing.interface import print_receipt
from apps.printing.pdf_backend import PrinterDependencyMissing

from .models import HeldSale, Sale
from .receipt_data import build_receipt_context
from .serializers import HeldSaleSerializer, SaleSerializer, VoidSaleSerializer


class BranchScopedQuerysetMixin:
    """Filters every queryset by the request's branch (see apps.inventory)."""

    def get_queryset(self):
        return super().get_queryset().filter(branch_id=self.request.branch_id)


class SaleViewSet(BranchScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = Sale.objects.select_related("cashier").prefetch_related("line_items__product")
    serializer_class = SaleSerializer
    permission_classes = [IsCashierOrAbove]
    # Sales are immutable once created except via /void/ — no PATCH/PUT/DELETE route.
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        if getattr(self.request.user, "role", None) == ROLE_CASHIER:
            qs = qs.filter(cashier=self.request.user)
        return self._apply_history_filters(qs)

    def _apply_history_filters(self, qs):
        """
        Query-param filtering for GET /sales/ — added for the Sales
        History screen (new this session, not one of the original
        7 design-doc screens; see project instructions). No
        DjangoFilterBackend/SearchFilter is used anywhere in this
        project (see apps.inventory.ProductViewSet's commented-out
        variant) — manual parsing here matches that established
        convention instead of introducing a dependency for one
        endpoint.

        Every param is optional and silently ignored if absent,
        malformed, or not a recognised choice — a bad filter value
        should never 400 or 500 a list endpoint, it should just not
        filter on that dimension.
        """
        params = self.request.query_params

        date_from = parse_date(params.get("date_from") or "")
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)

        date_to = parse_date(params.get("date_to") or "")
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        payment_method = params.get("payment_method")
        if payment_method in dict(Sale.PAYMENT_METHOD_CHOICES):
            qs = qs.filter(payment_method=payment_method)

        status_param = params.get("status")
        if status_param in dict(Sale.STATUS_CHOICES):
            qs = qs.filter(status=status_param)

        search = (params.get("search") or "").strip()
        if search:
            qs = qs.filter(reference__icontains=search)

        return qs

    @action(detail=True, methods=["post"], permission_classes=[IsManagerOrOwner])
    def void(self, request, pk=None):
        sale = self.get_object()
        serializer = VoidSaleSerializer(data=request.data, context={"sale": sale, "request": request})
        serializer.is_valid(raise_exception=True)
        sale = serializer.save()
        return Response(SaleSerializer(sale, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["get"])
    def receipt(self, request, pk=None):
        # apps.printing now exists (built this session) — un-stubbed from
        # the 503 apps.auth_users.LoadTemplateView-style placeholder.
        # print_receipt() is the abstracted printer interface (design doc
        # 8.4); this view never touches a backend module directly, so a
        # future PRINTER_BACKEND="thermal" switch needs no changes here.
        sale = self.get_object()
        sale_data = build_receipt_context(sale)
        try:
            pdf_bytes = print_receipt(sale_data)
        except PrinterDependencyMissing as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{sale.reference}.pdf"'
        return response


class HeldSaleViewSet(BranchScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = HeldSale.objects.select_related("cashier")
    serializer_class = HeldSaleSerializer
    permission_classes = [IsCashierOrAbove]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        if getattr(self.request.user, "role", None) == ROLE_CASHIER:
            qs = qs.filter(cashier=self.request.user)
        return qs

    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        held_sale = self.get_object()
        cart_data = held_sale.cart_data
        held_sale.delete()  # hard delete — transient by design, not soft-deleted
        return Response(cart_data)
