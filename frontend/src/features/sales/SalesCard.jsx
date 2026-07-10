import XAFAmount from "../../components/XAFAmount";
import { PaymentMethodBadge, SaleStatusBadge } from "./SaleBadges";

function formatDateTime(iso) {
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const time = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
  return `${dd}/${mm}/${d.getFullYear()} · ${time}`;
}

export default function SalesCard({ sale, showCashier, onOpen }) {
  return (
    <div
      className={`sh-card${sale.status === "voided" ? " voided" : ""}`}
      onClick={() => onOpen(sale.id)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") onOpen(sale.id);
      }}
    >
      <div className="sh-card-top">
        <span className="sh-card-ref">{sale.reference}</span>
        <SaleStatusBadge status={sale.status} />
      </div>
      <div className="sh-card-total">
        <XAFAmount value={sale.total_amount} />
      </div>
      <div className="sh-card-meta">{formatDateTime(sale.created_at)}</div>
      <div className="sh-card-meta">
        {sale.line_items.length} item{sale.line_items.length === 1 ? "" : "s"}
        {showCashier && ` · ${sale.cashier_name}`}
      </div>
      <PaymentMethodBadge method={sale.payment_method} />
    </div>
  );
}
