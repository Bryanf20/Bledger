import { useMemo, useState } from "react";
import XAFAmount from "../../components/XAFAmount";
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
export default function SupplierDetail({ supplier, purchases, isLoading, onEditSupplier, onSuccess, onError }) {
  const [showForm, setShowForm] = useState(false);
  const [viewingPurchaseId, setViewingPurchaseId] = useState(null);

  const stats = useMemo(() => {
    const unpaidCount = purchases.filter((p) => p.payment_status !== "paid").length;
    const lastPurchase = purchases[0] ?? null;
    return { unpaidCount, lastPurchase };
  }, [purchases]);

  const viewingPurchase = viewingPurchaseId ? purchases.find((p) => p.id === viewingPurchaseId) ?? null : null;

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
          <div className="sup-detail-name">{supplier.name}</div>
          <div className="sup-detail-meta">
            {supplier.phone && <span>📞 {supplier.phone}</span>}
            {supplier.area && <span>📍 {supplier.area}</span>}
            <span>Last purchase: {stats.lastPurchase ? formatDate(stats.lastPurchase.purchase_date) : "—"}</span>
          </div>
        </div>
        <div className="sup-detail-header-actions">
          <button type="button" className="sup-row-btn" onClick={onEditSupplier}>Edit</button>
          <button type="button" className="sup-hdr-btn" onClick={() => setShowForm((v) => !v)}>
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
    </div>
  );
}
