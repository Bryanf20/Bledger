import XAFAmount from "../../components/XAFAmount";
import { PaymentMethodBadge, SaleStatusBadge } from "./SaleBadges";

function formatDateTime(iso) {
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const time = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
  return `${dd}/${mm}/${d.getFullYear()} · ${time}`;
}

// Empty state is handled once by the parent screen (covers both
// table and card view identically) -- this component always renders
// a populated table.
export default function SalesTable({ sales, showCashier, onOpen }) {
  return (
    <table className="sh-table">
      <thead>
        <tr>
          <th>Reference</th>
          <th>Date &amp; time</th>
          {showCashier && <th>Cashier</th>}
          <th>Items</th>
          <th>Payment</th>
          <th>Total</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {sales.map((sale) => (
          <tr
            key={sale.id}
            className={`sh-row${sale.status === "voided" ? " voided" : ""}`}
            onClick={() => onOpen(sale.id)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") onOpen(sale.id);
            }}
          >
            <td className="sh-cell-ref">{sale.reference}</td>
            <td>{formatDateTime(sale.created_at)}</td>
            {showCashier && <td>{sale.cashier_name}</td>}
            <td>{sale.line_items.length}</td>
            <td>
              <PaymentMethodBadge method={sale.payment_method} />
            </td>
            <td className="sh-cell-total">
              <XAFAmount value={sale.total_amount} />
            </td>
            <td>
              <SaleStatusBadge status={sale.status} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
