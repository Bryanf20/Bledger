"""
Suppliers & Purchases views — design doc B.4 / API E.4.

Unlike inventory (cashier: read-only) or sales (cashier: full POS
access), the Suppliers & Purchases screen doesn't appear on the
cashier's UI at all (design doc B.4 is a manager/owner-only
master-detail screen) and unit_cost is financial data cashiers aren't
shown elsewhere (e.g. Product exposes retail/bulk prices, never cost).
So the whole app is gated at Manager+ rather than following inventory's
read/write split.
"""
from django.db.models import Count, Sum
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.permissions import IsManagerOrOwner

from .models import Purchase, Supplier
from .serializers import PurchaseSerializer, RecordPurchasePaymentSerializer, SupplierSerializer


class BranchScopedQuerysetMixin:
    """Filters every queryset by the request's branch (see apps.inventory, apps.sales)."""

    def get_queryset(self):
        return super().get_queryset().filter(branch_id=self.request.branch_id)


class SupplierViewSet(BranchScopedQuerysetMixin, viewsets.ModelViewSet):
    """
    GET/POST /suppliers/, PATCH /suppliers/{id}/ per API E.4.
    purchase_count / total_spent are annotated on the queryset here
    (not in the serializer) so list responses don't run a per-row
    aggregate query — see SupplierSerializer's docstring.
    """
    serializer_class = SupplierSerializer
    queryset = Supplier.objects.all()
    permission_classes = [IsAuthenticated, IsManagerOrOwner]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        # Explicit .order_by("name") because annotate()-ing aggregates
        # onto a queryset that relies on Meta.ordering alone triggers
        # DRF's UnorderedObjectListWarning under pagination — the
        # aggregation doesn't clear Meta.ordering, but it's not
        # something to rely on implicitly either.
        return (
            super()
            .get_queryset()
            .annotate(
                purchase_count=Count("purchases", distinct=True),
                total_spent=Sum("purchases__total_amount"),
            )
            .order_by("name")
        )

    def perform_create(self, serializer):
        serializer.save(branch_id=self.request.branch_id)


class PurchaseViewSet(BranchScopedQuerysetMixin, viewsets.ModelViewSet):
    """
    GET/POST /purchases/ per API E.4 — atomic Purchase + line items +
    stock_level increment (see PurchaseSerializer.create()). No
    PATCH/DELETE route: like a Sale, a recorded purchase is a permanent
    financial record once it's updated the stock ledger. The one
    exception is the record_payment action below, a narrow purpose-built
    mutation for amount_paid/payment_status only — see
    RecordPurchasePaymentSerializer's docstring for why this isn't a
    general PATCH.
    """
    serializer_class = PurchaseSerializer
    queryset = Purchase.objects.select_related("supplier", "recorded_by").prefetch_related(
        "line_items__product", "payments__recorded_by"
    )
    permission_classes = [IsAuthenticated, IsManagerOrOwner]
    http_method_names = ["get", "post", "head", "options"]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    @action(detail=True, methods=["post"], url_path="record-payment")
    def record_payment(self, request, pk=None):
        """
        POST /purchases/{id}/record-payment/ { amount, payment_date?, note? }
        -> updated Purchase (with the new payment in its `payments` list).
        Same permission_classes as the rest of this viewset (Manager+).
        """
        purchase = self.get_object()
        serializer = RecordPurchasePaymentSerializer(
            data=request.data, context={"purchase": purchase, "request": request}
        )
        serializer.is_valid(raise_exception=True)
        updated_purchase = serializer.save()
        return Response(PurchaseSerializer(updated_purchase, context={"request": request}).data)
    