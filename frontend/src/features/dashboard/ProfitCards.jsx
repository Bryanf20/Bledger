import XAFAmount from "../../components/XAFAmount";
import {
  useAgedDebt,
  useLowMargin,
  useMarginSummary,
  useStockValuation,
  useVarianceSummary,
} from "../../hooks/useDashboard";

// Phase 2 reporting cards (§3.4 variance, §7A.6 margin/valuation, §4.5
// aged debt). Manager+ — rendered inside DashboardScreen's manager view.
export default function ProfitCards({ period }) {
  const margin = useMarginSummary(period);
  const variance = useVarianceSummary(period);
  const valuation = useStockValuation();
  const lowMargin = useLowMargin();
  const agedDebt = useAgedDebt();

  const m = margin.data;
  const v = variance.data;
  const val = valuation.data;
  const low = lowMargin.data?.products ?? [];
  const debt = agedDebt.data ?? [];
  const totalDebt = debt.reduce((s, r) => s + r.balance, 0);

  return (
    <div className="dash-profit-cards">
      {/* Gross margin */}
      <div className="dash-card">
        <div className="dash-card-title">Gross margin ({period})</div>
        {margin.isLoading ? (
          <div className="dash-card-empty">Loading…</div>
        ) : (
          <>
            <div className="dash-profit-big">
              <XAFAmount value={m?.gross_margin ?? 0} />
              {m?.margin_pct != null && <span className="dash-profit-pct"> · {m.margin_pct}%</span>}
            </div>
            <div className="dash-profit-sub">
              Revenue <XAFAmount value={m?.revenue ?? 0} /> − cost <XAFAmount value={m?.cogs ?? 0} />
            </div>
            {m?.uncosted_revenue > 0 && (
              <div className="dash-profit-note">
                <XAFAmount value={m.uncosted_revenue} /> of sales excluded (cost not set)
              </div>
            )}
          </>
        )}
      </div>

      {/* Stock valuation */}
      <div className="dash-card">
        <div className="dash-card-title">Stock value (now)</div>
        {valuation.isLoading ? (
          <div className="dash-card-empty">Loading…</div>
        ) : (
          <>
            <div className="dash-profit-big"><XAFAmount value={val?.stock_value ?? 0} /></div>
            <div className="dash-profit-sub">
              {val?.costed_products ?? 0} products valued
              {val?.cost_unknown_products ? ` · ${val.cost_unknown_products} need a cost` : ""}
            </div>
          </>
        )}
      </div>

      {/* Negotiated variance */}
      <div className="dash-card">
        <div className="dash-card-title">Haggling ({period})</div>
        {variance.isLoading ? (
          <div className="dash-card-empty">Loading…</div>
        ) : (
          <div className="dash-profit-sub">
            <div>Surplus collected: <XAFAmount value={v?.total_surplus ?? 0} /></div>
            <div>Discounts given: <XAFAmount value={v?.total_discount ?? 0} /></div>
            <div>Net: <XAFAmount value={v?.net_variance ?? 0} /></div>
          </div>
        )}
      </div>

      {/* Outstanding credit */}
      <div className="dash-card">
        <div className="dash-card-title">Owed by customers</div>
        {agedDebt.isLoading ? (
          <div className="dash-card-empty">Loading…</div>
        ) : debt.length === 0 ? (
          <div className="dash-card-empty">No outstanding credit.</div>
        ) : (
          <>
            <div className="dash-profit-big"><XAFAmount value={totalDebt} /></div>
            <div className="dash-profit-sub">{debt.length} customer{debt.length === 1 ? "" : "s"} owe you</div>
          </>
        )}
      </div>

      {/* Low / negative margin */}
      <div className="dash-card">
        <div className="dash-card-title">Thin / loss-making products</div>
        {lowMargin.isLoading ? (
          <div className="dash-card-empty">Loading…</div>
        ) : low.length === 0 ? (
          <div className="dash-card-empty">All products within a healthy margin.</div>
        ) : (
          <div className="dash-low-list">
            {low.slice(0, 6).map((p) => (
              <div key={p.product_id} className={`dash-low-row${p.at_or_below_cost ? " loss" : ""}`}>
                <span>{p.name}</span>
                <span>{p.margin_pct}%{p.at_or_below_cost ? " ⚠" : ""}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
