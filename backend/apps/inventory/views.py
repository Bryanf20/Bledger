"""
Inventory views — design doc Part C.2 / API reference E.2.

Role split mirrors the Inventory screen (design doc B.3): owner/manager
get full write access; cashier gets read-only (the "Add product" button
and Adjust/Edit row actions are hidden client-side, and enforced here).
"""
from django.db import transaction
from django.db.models import Q
from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.core.permissions import IsCashierOrAbove, IsManagerOrOwner
from apps.sync.models import OutboxEntry
from apps.sync.utils import write_outbox_entry

from .models import (
    HQ_BRANCH_ID,
    BranchPriceOverride,
    Category,
    Product,
    ProductPriceHistory,
    StockAdjustment,
)
from .serializers import (
    BranchPriceOverrideSerializer,
    CategorySerializer,
    ProductSerializer,
    StockAdjustmentSerializer,
)


class BranchScopedQuerysetMixin:
    """
    Scopes every list/detail queryset to the requesting branch. Product
    additionally includes the HQ catalogue (branch_id=HQ_BRANCH_ID) per
    Feasibility doc Section 6 — branches read the HQ catalogue read-only
    and layer local price overrides on top. In Phase 1 standalone,
    request.branch_id is the single fixed BRANCH_ID for the install, so
    this is close to a no-op; it's the seam Phase 2 multi-branch relies on.
    """
    include_hq_catalogue = False

    def get_queryset(self):
        qs = super().get_queryset()
        branch_id = self.request.branch_id
        if self.include_hq_catalogue:
            return qs.filter(Q(branch_id=branch_id) | Q(branch_id=HQ_BRANCH_ID))
        return qs.filter(branch_id=branch_id)


class CategoryViewSet(BranchScopedQuerysetMixin, viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    queryset = Category.objects.all()

    def get_permissions(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return [IsAuthenticated(), IsManagerOrOwner()]
        return [IsAuthenticated(), IsCashierOrAbove()]

    # Categories are part of the catalogue layer that propagates
    # HQ -> branches (feasibility §6), so every mutation needs an outbox
    # entry. These were missing until Phase 2 §8.2 — the writes worked
    # locally but would never have reached the cloud.
    def perform_create(self, serializer):
        with transaction.atomic():
            instance = serializer.save(branch_id=self.request.branch_id)
            write_outbox_entry(instance=instance, operation=OutboxEntry.INSERT)

    def perform_update(self, serializer):
        with transaction.atomic():
            instance = serializer.save()
            write_outbox_entry(instance=instance, operation=OutboxEntry.UPDATE)

    def perform_destroy(self, instance):
        with transaction.atomic():
            instance.soft_delete()
            # DELETE, not UPDATE: soft_delete() sets deleted_at, and the
            # cloud needs a tombstone it can propagate to other branches
            # rather than an ordinary field change.
            write_outbox_entry(instance=instance, operation=OutboxEntry.DELETE)


class ProductViewSet(BranchScopedQuerysetMixin, viewsets.ModelViewSet):
    """
    GET/POST /products/, PATCH /products/{id}/ per API E.2. DELETE
    deactivates rather than deletes (design doc B.3) so sale history
    stays intact — PATCH is_active back to true to reactivate.
    """
    serializer_class = ProductSerializer
    queryset = Product.objects.select_related("category").all()
    include_hq_catalogue = True
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.request.method in ("POST", "PATCH", "DELETE"):
            return [IsAuthenticated(), IsManagerOrOwner()]
        return [IsAuthenticated(), IsCashierOrAbove()]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    # Product create/edit are the catalogue writes that must reach
    # branches (feasibility §6) — added in Phase 2 §8.2. Deactivation
    # (perform_destroy) already wrote an entry before this change.
    def perform_create(self, serializer):
        with transaction.atomic():
            extra = {"branch_id": self.request.branch_id, "source": "manual"}
            # An explicit average_cost at creation is a real cost basis
            # (opening stock the owner already knows the cost of) — flag
            # it so it isn't treated as "cost unknown" (§7A.8).
            if "average_cost" in serializer.validated_data:
                extra["cost_is_set"] = True
            instance = serializer.save(**extra)
            write_outbox_entry(instance=instance, operation=OutboxEntry.INSERT)
            # Opening price is the first row in the product's price
            # history (§7A.1).
            self._record_price_history(instance, previous=None)

    def perform_update(self, serializer):
        # Capture the pre-save prices so we only log history on a real
        # change (the instance still holds old values before save()).
        before = {
            "retail_price": serializer.instance.retail_price,
            "bulk_price": serializer.instance.bulk_price,
            "bulk_min_qty": serializer.instance.bulk_min_qty,
        }
        with transaction.atomic():
            extra = {}
            if "average_cost" in serializer.validated_data:
                # Manual cost correction — a deliberate owner entry, so
                # mark the basis as known (§7A.8).
                extra["cost_is_set"] = True
            instance = serializer.save(**extra)
            write_outbox_entry(instance=instance, operation=OutboxEntry.UPDATE)
            self._record_price_history(instance, previous=before)

    def _record_price_history(self, product, *, previous):
        """
        Append a ProductPriceHistory row (§7A.1). `previous=None` for a
        create (always log the opening price); on update, log only if a
        price field actually changed.
        """
        if previous is not None and (
            previous["retail_price"] == product.retail_price
            and previous["bulk_price"] == product.bulk_price
            and previous["bulk_min_qty"] == product.bulk_min_qty
        ):
            return
        history = ProductPriceHistory.objects.create(
            branch_id=product.branch_id,
            product=product,
            retail_price=product.retail_price,
            bulk_price=product.bulk_price,
            bulk_min_qty=product.bulk_min_qty,
            changed_by=self.request.user,
        )
        write_outbox_entry(instance=history, operation=OutboxEntry.INSERT)

    def perform_destroy(self, instance):
        # Deactivation, not deletion (design doc B.3) -- so this stays
        # an UPDATE rather than a DELETE tombstone: the row still exists
        # and still appears on historical receipts, it just drops out of
        # the POS grid.
        with transaction.atomic():
            instance.is_active = False
            instance.save(update_fields=["is_active", "updated_at", "version"])
            # branch_id defaults to instance.branch_id inside
            # write_outbox_entry() -- not request.branch_id, since a
            # deactivated product's own branch_id is the correct outbox
            # scope even in the (currently theoretical) case of a manager
            # deactivating an HQ-catalogue row surfaced through
            # BranchScopedQuerysetMixin's include_hq_catalogue union.
            write_outbox_entry(instance=instance, operation=OutboxEntry.UPDATE)


class BranchPriceOverrideViewSet(
    BranchScopedQuerysetMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """UPSERT-on-create per API E.2 — see serializer for the upsert logic."""
    serializer_class = BranchPriceOverrideSerializer
    queryset = BranchPriceOverride.objects.select_related("product").all()
    permission_classes = [IsAuthenticated, IsManagerOrOwner]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


class StockAdjustmentViewSet(
    BranchScopedQuerysetMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    Read-only audit log + create adjustment per API E.2. No update or
    delete endpoint exists — adjustments are permanent once made.
    """
    serializer_class = StockAdjustmentSerializer
    queryset = StockAdjustment.objects.select_related("product", "adjusted_by").all()

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsManagerOrOwner()]
        return [IsAuthenticated(), IsCashierOrAbove()]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context
