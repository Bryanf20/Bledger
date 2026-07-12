import XAFAmount from "../../components/XAFAmount";
import { PaymentStatusBadge } from "./SupplierBadges";
import RecordPaymentForm from "./RecordPaymentForm";

function formatDate(isoDate) {
  const d = new Date(`${isoDate}T00:00:00`);
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

// Same "inline side panel, not a modal" convention as
// SupplierFormPanel/InventoryScreen's drawers -- transparent backdrop,
// click-outside-to-close, reuses .sup-drawer-backdrop/.sup-drawer/
// .sup-drawer-header/.sup-form-scroll wholesale, no new drawer-shell
// CSS needed.
//
// `purchase` is looked up fresh from the live `purchases` list by
// SupplierDetail (by id) rather than a snapshot taken at the moment
// the panel opened -- so after RecordPaymentForm's mutation invalidates
// and refetches ["purchases"], this panel re-renders with the updated
// balance_due/payments automatically, no manual sync needed. If a
// payment brings balance_due to 0, the form below just stops
// rendering on the next render, same reactivity.
export default function PurchaseDetailPanel({ purchase, onClose, onSuccess, onError }) {
  return (
    <div className="sup-drawer-backdrop" onClick={onClose}>
      <div className="sup-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="sup-drawer-header">
          <span>Purchase — {formatDate(purchase.purchase_date)}</span>
          <button type="button" className="sup-icon-btn" onClick={onClose}>Close</button>
        </div>

        <div className="sup-form-scroll">
          <div className="sup-detail-panel-summary">
            <div className="sup-detail-panel-row">
              <span>Supplier</span>
              <span>{purchase.supplier_name}</span>
            </div>
            <div className="sup-detail-panel-row">
              <span>Total</span>
              <span><XAFAmount value={purchase.total_amount} /></span>
            </div>
            <div className="sup-detail-panel-row">
              <span>Paid</span>
              <span><XAFAmount value={purchase.amount_paid} /></span>
            </div>
            <div className="sup-detail-panel-row">
              <span>Balance</span>
              <span>{purchase.balance_due > 0 ? <XAFAmount value={purchase.balance_due} /> : "—"}</span>
            </div>
            <div className="sup-detail-panel-row">
              <span>Status</span>
              <PaymentStatusBadge status={purchase.payment_status} amountPaid={purchase.amount_paid} />
            </div>
            {purchase.recorded_by_name && (
              <div className="sup-detail-panel-row">
                <span>Recorded by</span>
                <span>{purchase.recorded_by_name}</span>
              </div>
            )}
          </div>

          <div>
            <div className="sup-detail-panel-section-title">Items</div>
            <table className="sup-table">
              <thead>
                <tr>
                  <th>Product</th>
                  <th>Qty</th>
                  <th>Unit cost</th>
                  <th>Line total</th>
                </tr>
              </thead>
              <tbody>
                {purchase.line_items.map((li) => (
                  <tr key={li.id}>
                    <td>{li.product_name}</td>
                    <td>{li.quantity}</td>
                    <td><XAFAmount value={li.unit_cost} /></td>
                    <td className="sup-cell-total"><XAFAmount value={li.line_total} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div>
            <div className="sup-detail-panel-section-title">Payments</div>
            {purchase.payments.length === 0 ? (
              <div className="sup-empty-state">No payments recorded yet.</div>
            ) : (
              <table className="sup-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Amount</th>
                    <th>Recorded by</th>
                    <th>Note</th>
                  </tr>
                </thead>
                <tbody>
                  {purchase.payments.map((p) => (
                    <tr key={p.id}>
                      <td>{formatDate(p.payment_date)}</td>
                      <td className="sup-cell-total"><XAFAmount value={p.amount} /></td>
                      <td>{p.recorded_by_name ?? "—"}</td>
                      <td className="sup-cell-items">{p.note || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {purchase.balance_due > 0 && (
            <RecordPaymentForm purchase={purchase} onSuccess={onSuccess} onError={onError} />
          )}
        </div>
      </div>
    </div>
  );
}
