from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import ROLE_CASHIER, IsCashierOrAbove, IsManagerOrOwner

from .models import HeldSale, Sale
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
        # apps.printing doesn't exist yet (design doc Part C). Stubbed
        # the same way apps.auth_users.LoadTemplateView was stubbed
        # before apps.inventory existed — un-stub when printing is built.
        return Response(
            {"detail": "Receipt generation is not available until the printing app is built."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


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
