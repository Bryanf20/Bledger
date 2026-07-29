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
from apps.sync.models import OutboxEntry
from apps.sync.utils import write_outbox_entry

from .models import Purchase, PurchaseOrder, Supplier
from .serializers import (
    PurchaseOrderSerializer,
    PurchaseSerializer,
    ReceivePurchaseOrderSerializer,
    RecordPurchasePaymentSerializer,
    SupplierSerializer,
)


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


class PurchaseOrderViewSet(BranchScopedQuerysetMixin, viewsets.ModelViewSet):
    """
    GET/POST /purchase-orders/ (Phase 2 design §6). Manager+, like the rest of
    this app. A PO touches no stock; goods enter through the `receive` action,
    which creates a normal Purchase (the single stock-moving path). No general
    PATCH/DELETE — state changes go through the send / cancel / receive
    actions, keeping status transitions auditable.
    """

    serializer_class = PurchaseOrderSerializer
    queryset = PurchaseOrder.objects.select_related("supplier", "created_by").prefetch_related(
        "line_items__product", "receipts"
    )
    permission_classes = [IsAuthenticated, IsManagerOrOwner]
    http_method_names = ["get", "post", "head", "options"]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def _transition(self, request, target, allowed_from):
        po = self.get_object()
        if po.status not in allowed_from:
            return Response(
                {"detail": f"A {po.status} purchase order can't move to {target}."},
                status=400,
            )
        po.status = target
        po.save(update_fields=["status", "updated_at", "version"])
        write_outbox_entry(instance=po, operation=OutboxEntry.UPDATE, branch_id=po.branch_id)
        return Response(PurchaseOrderSerializer(po, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="send")
    def send(self, request, pk=None):
        """POST /purchase-orders/{id}/send/ — draft -> sent."""
        return self._transition(request, PurchaseOrder.SENT, {PurchaseOrder.DRAFT})

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        """POST /purchase-orders/{id}/cancel/ — cancel an open PO."""
        return self._transition(
            request,
            PurchaseOrder.CANCELLED,
            {PurchaseOrder.DRAFT, PurchaseOrder.SENT, PurchaseOrder.PARTIALLY_RECEIVED},
        )

    @action(detail=True, methods=["post"], url_path="receive")
    def receive(self, request, pk=None):
        """
        POST /purchase-orders/{id}/receive/
          { receipts: [{ line, quantity }], purchase_date?, amount_paid? }
        Creates a Purchase for the received goods, links it, advances the PO.
        """
        po = self.get_object()
        serializer = ReceivePurchaseOrderSerializer(
            data=request.data, context={"purchase_order": po, "request": request}
        )
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(PurchaseOrderSerializer(updated, context={"request": request}).data)
