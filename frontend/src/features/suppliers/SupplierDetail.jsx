import { useMemo, useState } from "react";
import XAFAmount from "../../components/XAFAmount";
import InlineConfirm from "../../components/InlineConfirm";
import { useUpdateSupplier } from "../../hooks/useSuppliers";
import { SupplierInactiveBadge } from "./SupplierBadges";
import PurchaseHistoryTable from "./PurchaseHistoryTable";
import RecordPurchaseForm from "./RecordPurchaseForm";
import PurchaseDetailPanel from "./PurchaseDetailPanel";

function formatDate(isoDate) {
  const d = new Date(`${isoDate}T00:00:00`);
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

// `purchases` arrives already scoped to this supplier and sorted
// newest-first (see SuppliersScreen). purchase_count / total_spent
// for the stats strip's first two columns come from the Supplier
// object itself (server-annotated); only "unpaid/partial count" is
// computed here client-side, since that's not annotated server-side.
//
// `viewingPurchaseId` (added this session) holds an id, not a
// snapshot of the purchase object -- PurchaseDetailPanel is handed
// `purchases.find(...)` fresh on every render, so once
// RecordPaymentForm's mutation invalidates ["purchases"] and it
// refetches, the open panel picks up the new balance_due/payments
// automatically instead of showing stale data until it's closed and
// reopened.
export default function SupplierDetail({ supplier, purchases, isLoading, onEditSupplier, onBack, onSuccess, onError }) {
  const [showForm, setShowForm] = useState(false);
  const [viewingPurchaseId, setViewingPurchaseId] = useState(null);
  const [confirmingDeactivate, setConfirmingDeactivate] = useState(false);
  const updateSupplier = useUpdateSupplier();

  const stats = useMemo(() => {
    const unpaidCount = purchases.filter((p) => p.payment_status !== "paid").length;
    const lastPurchase = purchases[0] ?? null;
    return { unpaidCount, lastPurchase };
  }, [purchases]);

  const viewingPurchase = viewingPurchaseId ? purchases.find((p) => p.id === viewingPurchaseId) ?? null : null;

  // Deactivation is a plain PATCH { is_active } via the same
  // useUpdateSupplier mutation the edit drawer uses -- Supplier rows
  // are never deleted (purchase history references them), matching
  // Product's deactivate-not-delete convention.
  async function handleToggleActive() {
    try {
      await updateSupplier.mutateAsync({
        id: supplier.id,
        payload: { is_active: !supplier.is_active },
      });
      setConfirmingDeactivate(false);
      setShowForm(false);
      onSuccess(supplier.is_active ? `${supplier.name} deactivated.` : `${supplier.name} reactivated.`);
    } catch (err) {
      setConfirmingDeactivate(false);
      onError(err, "Couldn't update that supplier.");
    }
  }

  if (isLoading) {
    return (
      <div className="sup-detail">
        <div className="sup-empty-state">Loading…</div>
      </div>
    );
  }

  if (!supplier) {
    return (
      <div className="sup-detail">
        <div className="sup-empty-state">No suppliers yet — add one to record your first purchase.</div>
      </div>
    );
  }

  return (
    <div className="sup-detail">
      <div className="sup-detail-header">
        <div className="sup-detail-header-info">
          {/* Only rendered <720px (display:none above that) -- returns
              to the supplier list in the one-panel-at-a-time flow. */}
          <button type="button" className="sup-back-btn" onClick={onBack}>
            ← Suppliers
          </button>
          <div className="sup-detail-name">
            {supplier.name} {!supplier.is_active && <SupplierInactiveBadge />}
          </div>
          <div className="sup-detail-meta">
            {supplier.phone && <span>📞 {supplier.phone}</span>}
            {supplier.area && <span>📍 {supplier.area}</span>}
            <span>Last purchase: {stats.lastPurchase ? formatDate(stats.lastPurchase.purchase_date) : "—"}</span>
          </div>
        </div>
        <div className="sup-detail-header-actions">
          <button type="button" className="sup-row-btn" onClick={onEditSupplier}>Edit</button>
          <button
            type="button"
            className="sup-row-btn"
            disabled={updateSupplier.isPending}
            onClick={() => (supplier.is_active ? setConfirmingDeactivate(true) : handleToggleActive())}
          >
            {supplier.is_active
              ? "Deactivate"
              : updateSupplier.isPending
                ? "Reactivating…"
                : "Reactivate"}
          </button>
          <button
            type="button"
            className="sup-hdr-btn"
            disabled={!supplier.is_active}
            title={supplier.is_active ? undefined : "Reactivate this supplier to record a purchase."}
            onClick={() => setShowForm((v) => !v)}
          >
            {showForm ? "Cancel" : "+ Record purchase"}
          </button>
        </div>
      </div>

      <div className="sup-stats-strip">
        <div className="sup-stat">
          <div className="sup-stat-label">Total purchases</div>
          <div className="sup-stat-value">{supplier.purchase_count}</div>
        </div>
        <div className="sup-stat">
          <div className="sup-stat-label">Total spent</div>
          <div className="sup-stat-value"><XAFAmount value={supplier.total_spent} /></div>
        </div>
        <div className="sup-stat">
          <div className="sup-stat-label">Unpaid / partial</div>
          <div className={`sup-stat-value${stats.unpaidCount > 0 ? " warning" : ""}`}>{stats.unpaidCount}</div>
        </div>
      </div>

      <div className="sup-detail-scroll">
        <PurchaseHistoryTable purchases={purchases} onSelectPurchase={(p) => setViewingPurchaseId(p.id)} />

        {showForm && (
          <RecordPurchaseForm
            supplier={supplier}
            onCancel={() => setShowForm(false)}
            onSuccess={(message) => {
              setShowForm(false);
              onSuccess(message);
            }}
            onError={onError}
          />
        )}
      </div>

      {viewingPurchase && (
        <PurchaseDetailPanel
          purchase={viewingPurchase}
          onClose={() => setViewingPurchaseId(null)}
          onSuccess={onSuccess}
          onError={onError}
        />
      )}

      {confirmingDeactivate && (
        <InlineConfirm
          title={`Deactivate ${supplier.name}?`}
          subtitle="Their purchase history is kept, but new purchases can't be recorded until they're reactivated."
          onCancel={() => setConfirmingDeactivate(false)}
          onConfirm={handleToggleActive}
          confirmLabel="Deactivate"
          confirmPendingLabel="Deactivating…"
          isPending={updateSupplier.isPending}
          danger
        />
      )}
    </div>
  );
}
