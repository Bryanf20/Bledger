import XAFAmount from "../../components/XAFAmount";

// "2x2 grid of payment method cards (Cash, MTN MoMo, Orange Money,
// Other), each showing amount, percentage of total, and a
// proportional colored bar" (UI Design Reference Screen 5) --
// "first-class widget, not buried in a report" per design doc B.5.
//
// PaymentBreakdownView only returns rows for methods with at least
// one sale in the period (a plain .values().annotate() grouping, no
// zero-fill) -- this component maps over the full fixed 4-method list
// so the grid always shows all four cards, defaulting missing methods
// to 0 rather than omitting them from a "2x2 grid" that would
// otherwise look broken with e.g. 2 or 3 cards on a slow day.
const METHODS = [
  { key: "cash", label: "Cash", variant: "neutral" },
  { key: "mtn_momo", label: "MTN MoMo", variant: "warning" },
  { key: "orange_money", label: "Orange Money", variant: "info" },
  { key: "other", label: "Other", variant: "neutral" },
];

export default function PaymentBreakdownCard({ data, isLoading }) {
  const rows = data ?? [];
  const totalRevenue = rows.reduce((sum, r) => sum + r.revenue, 0);

  return (
    <div className="dash-card">
      <div className="dash-card-title">Payment breakdown</div>

      {isLoading ? (
        <div className="dash-empty">Loading…</div>
      ) : totalRevenue === 0 ? (
        <div className="dash-empty">No sales in this period.</div>
      ) : (
        <div className="dash-payment-grid">
          {METHODS.map((m) => {
            const row = rows.find((r) => r.payment_method === m.key);
            const revenue = row?.revenue ?? 0;
            const pct = totalRevenue ? Math.round((revenue / totalRevenue) * 100) : 0;
            return (
              <div className="dash-payment-cell" key={m.key}>
                <div className="dash-payment-cell-label">{m.label}</div>
                <div className="dash-payment-cell-amount">
                  <XAFAmount value={revenue} />
                </div>
                <div className="dash-payment-cell-pct">{pct}%</div>
                <div className="dash-payment-bar-track">
                  <div className={`dash-payment-bar dash-payment-bar-${m.variant}`} style={{ width: `${pct}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
