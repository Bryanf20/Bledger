import XAFAmount from "../../components/XAFAmount";
import { PaymentStatusBadge } from "./SupplierBadges";

function formatDate(isoDate) {
  // purchase_date is a DateField (YYYY-MM-DD, no time component) --
  // append T00:00:00 so the browser parses it in local time instead
  // of UTC, which can otherwise roll the displayed date back a day.
  const d = new Date(`${isoDate}T00:00:00`);
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

// "Items (free text summary)" per the UI Design Reference -- built
// from the real nested line_items (product_name × quantity), not a
// stored free-text field (Purchase has none).
function itemsSummary(purchase) {
  return purchase.line_items.map((li) => `${li.product_name} ×${li.quantity}`).join(", ");
}

// [DEVIATION -- FLAGGED] The 04_suppliers.html mockup shows a "Ref"
// column (P001, P002…), but backend/apps/suppliers/models.py's
// Purchase model has no reference field at all -- unlike Sale, which
// does have one. Verified against the real source before building;
// the column is omitted rather than fabricating a client-side
// reference that wouldn't mean anything.
//
// Balance column + row click added this session, alongside
// PurchaseDetailPanel: every row now opens the detail panel
// (items + payment history + the record-payment form when there's a
// balance) instead of a per-row "Record payment" button -- one entry
// point into one place that shows everything, rather than two
// separate flows for viewing vs. paying.
export default function PurchaseHistoryTable({ purchases, onSelectPurchase }) {
  if (!purchases.length) {
    return <div className="sup-empty-state">No purchases recorded yet for this supplier.</div>;
  }

  return (
    <table className="sup-table">
      <thead>
        <tr>
          <th>Date</th>
          <th>Items</th>
          <th>Total</th>
          <th>Status</th>
          <th>Balance</th>
        </tr>
      </thead>
      <tbody>
        {purchases.map((p) => (
          <tr key={p.id} className="sup-table-row-clickable" onClick={() => onSelectPurchase(p)}>
            <td>{formatDate(p.purchase_date)}</td>
            <td className="sup-cell-items">{itemsSummary(p)}</td>
            <td className="sup-cell-total"><XAFAmount value={p.total_amount} /></td>
            <td><PaymentStatusBadge status={p.payment_status} amountPaid={p.amount_paid} /></td>
            <td className="sup-cell-total">
              {p.balance_due > 0 ? <XAFAmount value={p.balance_due} /> : "—"}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
