"""
Customers & credit views (Phase 2 design §4).

Role split (§4.5): reading customers and their balances, registering a
customer, and receiving a payment are till activities (cashier+). Editing
a customer — crucially, setting or raising the credit_limit — is
manager+. So a cashier can add a walk-in credit customer, but that
customer starts with a 0 limit (every credit sale needs manager approval)
until a manager grants a limit.
"""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.permissions import IsCashierOrAbove, IsManagerOrOwner
from apps.sync.models import OutboxEntry
from apps.sync.utils import write_outbox_entry

from .models import Customer
from .serializers import (
    AgedDebtSerializer,
    CustomerSerializer,
    RecordCustomerPaymentSerializer,
)
from .services import aging_buckets, customer_balance


class BranchScopedQuerysetMixin:
    """Filters every queryset by the request's branch (see apps.suppliers)."""

    def get_queryset(self):
        return super().get_queryset().filter(branch_id=self.request.branch_id)


class CustomerViewSet(BranchScopedQuerysetMixin, viewsets.ModelViewSet):
    serializer_class = CustomerSerializer
    queryset = Customer.objects.prefetch_related("payments__recorded_by")
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_permissions(self):
        # This override takes precedence over an @action's own
        # permission_classes, so action-specific gating is handled here.
        # aged-debt is a manager+ debt report; PATCH (which can change
        # credit_limit) is manager+; everything else — list, retrieve,
        # create, record-payment — is cashier+ (till activities).
        if getattr(self, "action", None) == "aged_debt":
            return [IsAuthenticated(), IsManagerOrOwner()]
        if self.request.method == "PATCH":
            return [IsAuthenticated(), IsManagerOrOwner()]
        return [IsAuthenticated(), IsCashierOrAbove()]

    def perform_create(self, serializer):
        # A cashier may register a customer but not grant credit — the
        # limit starts at 0 regardless of what was posted, and only a
        # manager PATCH can raise it.
        extra = {"branch_id": self.request.branch_id}
        if not self.request.user.is_manager and not self.request.user.is_owner:
            extra["credit_limit"] = 0
        instance = serializer.save(**extra)
        write_outbox_entry(instance=instance, operation=OutboxEntry.INSERT)

    def perform_update(self, serializer):
        instance = serializer.save()
        write_outbox_entry(instance=instance, operation=OutboxEntry.UPDATE)

    @action(detail=True, methods=["post"], url_path="record-payment")
    def record_payment(self, request, pk=None):
        """POST /customers/{id}/record-payment/ — cashier+ (a till activity)."""
        customer = self.get_object()
        serializer = RecordCustomerPaymentSerializer(
            data=request.data, context={"customer": customer, "request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(CustomerSerializer(customer).data)

    @action(detail=False, methods=["get"], url_path="aged-debt", permission_classes=[IsAuthenticated, IsManagerOrOwner])
    def aged_debt(self, request):
        """
        GET /customers/aged-debt/ — every customer with an outstanding
        balance, split into 0–30 / 31–60 / 61+ day buckets (§4.5).
        Manager+ only: it's a debt report, not a till function.
        """
        rows = []
        for customer in self.get_queryset().filter(is_active=True):
            balance = customer_balance(customer)
            if balance <= 0:
                continue
            buckets = aging_buckets(customer)
            rows.append(
                {
                    "customer_id": customer.id,
                    "name": customer.name,
                    "phone": customer.phone,
                    "balance": balance,
                    "bucket_0_30": buckets["bucket_0_30"],
                    "bucket_31_60": buckets["bucket_31_60"],
                    "bucket_61_plus": buckets["bucket_61_plus"],
                }
            )
        rows.sort(key=lambda r: r["balance"], reverse=True)
        return Response(AgedDebtSerializer(rows, many=True).data)
