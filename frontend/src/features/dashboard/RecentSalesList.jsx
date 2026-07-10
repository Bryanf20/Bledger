import { useNavigate } from "react-router-dom";
import XAFAmount from "../../components/XAFAmount";
import { PaymentMethodBadge } from "./DashboardBadges";

function formatTime(iso) {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
}

// "Last few transactions with amount, time, item count, and payment
// method badge" (UI Design Reference Screen 5). fetchSales({}) via
// useRecentSales() already returns newest-first (BaseModel.Meta's
// -created_at default) -- sliced to 5 here rather than in the hook,
// so the hook stays a plain unfiltered fetch reusable at other sizes
// later if needed.
export default function RecentSalesList({ sales, isLoading }) {
  const navigate = useNavigate();
  const recent = (sales ?? []).slice(0, 5);

  return (
    <div className="dash-card">
      <div className="dash-card-title">Recent sales</div>

      {isLoading ? (
        <div className="dash-empty">Loading…</div>
      ) : recent.length === 0 ? (
        <div className="dash-empty">No sales yet.</div>
      ) : (
        <div className="dash-recent-list">
          {recent.map((sale) => (
            <div
              className="dash-recent-row"
              key={sale.id}
              onClick={() => navigate(`/receipt/${sale.id}`)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") navigate(`/receipt/${sale.id}`);
              }}
            >
              <div className="dash-recent-main">
                <span className="dash-recent-amount">
                  <XAFAmount value={sale.total_amount} />
                </span>
                <span className="dash-recent-meta">
                  {sale.line_items.length} item{sale.line_items.length === 1 ? "" : "s"} · {formatTime(sale.created_at)}
                </span>
              </div>
              <PaymentMethodBadge method={sale.payment_method} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
