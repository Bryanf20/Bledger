import { Link } from "react-router-dom";
import { StockSeverityDot } from "./DashboardBadges";

// "Compact list of low/out-of-stock products with a colored severity
// dot and an inline Restock shortcut button linking to the supplier
// screen" (UI Design Reference Screen 5). "Stock alerts are
// cashier-visible: this is the one dashboard widget cashiers can see
// ... so a cashier at the till knows what's out of stock without
// needing owner access."
//
// `showRestockLink` defaults true but DashboardScreen passes false
// for cashiers -- /suppliers is Manager+-gated (RoleGuard,
// minimumRole="manager"), so a cashier clicking it would just bounce
// straight back to /pos. [DEVIATION -- FLAGGED, not specified in the
// doc] hiding a dead-end control felt better than showing a button
// that silently redirects; the alert list itself still renders in
// full for cashiers either way.
export default function StockAlertsCard({ alerts, isLoading, showRestockLink = true }) {
  return (
    <div className="dash-card">
      <div className="dash-card-title">Stock alerts</div>

      {isLoading ? (
        <div className="dash-empty">Loading…</div>
      ) : !alerts || alerts.length === 0 ? (
        <div className="dash-empty">No low or out-of-stock products.</div>
      ) : (
        <div className="dash-alert-list">
          {alerts.map((a) => (
            <div className="dash-alert-row" key={a.product_id}>
              <StockSeverityDot status={a.status} />
              <div className="dash-alert-info">
                <div className="dash-alert-name">{a.product_name}</div>
                <div className="dash-alert-meta">
                  {a.stock_level} left · threshold {a.low_stock_threshold}
                </div>
              </div>
              {showRestockLink && (
                <Link to="/suppliers" className="dash-alert-restock-btn">
                  Restock
                </Link>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
