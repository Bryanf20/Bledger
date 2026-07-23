import XAFAmount from "../../components/XAFAmount";
import {
  useAgedDebt,
  useBrokeredSummary,
  useLowMargin,
  useMarginSummary,
  useStockValuation,
  useVarianceSummary,
} from "../../hooks/useDashboard";
import { usePnl } from "../../hooks/useFinances";

// Phase 2 reporting cards (§3.4 variance, §7A.6 margin/valuation, §4.5
// aged debt, §7C.4 net profit / expenses / brokered gains). Manager+ —
// rendered inside DashboardScreen's manager view.
export default function ProfitCards({ period }) {
  const margin = useMarginSummary(period);
  const variance = useVarianceSummary(period);
  const valuation = useStockValuation();
  const lowMargin = useLowMargin();
  const agedDebt = useAgedDebt();
  const pnl = usePnl(period); // net profit + expenses (manager+ since step 8f)
  const brokered = useBrokeredSummary(period);

  const m = margin.data;
  const v = variance.data;
  const val = valuation.data;
  const low = lowMargin.data?.products ?? [];
  const debt = agedDebt.data ?? [];
  const totalDebt = debt.reduce((s, r) => s + r.balance, 0);
  const p = pnl.data;
  const br = brokered.data;
  const expenseRows = p?.expenses_by_category ?? [];

  return (
    <div className="dash-profit-cards">
      {/* Net profit — the honest bottom line (§7C.4) */}
      <div className="dash-card dash-card-highlight">
        <div className="dash-card-title">Net profit ({period})</div>
        {pnl.isLoading ? (
          <div className="dash-card-empty">Loading…</div>
        ) : (
          <>
            <div className={`dash-profit-big${(p?.net_profit ?? 0) < 0 ? " dash-negative" : ""}`}>
              <XAFAmount value={p?.net_profit ?? 0} />
            </div>
            <div className="dash-profit-sub">
              Margin <XAFAmount value={p?.gross_margin ?? 0} /> − expenses <XAFAmount value={p?.total_expenses ?? 0} />
              {p?.total_income ? <> + income <XAFAmount value={p.total_income} /></> : null}
            </div>
          </>
        )}
      </div>

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

      {/* Expenses + by-category (§7C.4) */}
      <div className="dash-card">
        <div className="dash-card-title">Expenses ({period})</div>
        {pnl.isLoading ? (
          <div className="dash-card-empty">Loading…</div>
        ) : (p?.total_expenses ?? 0) === 0 ? (
          <div className="dash-card-empty">No expenses recorded.</div>
        ) : (
          <>
            <div className="dash-profit-big"><XAFAmount value={p.total_expenses} /></div>
            <div className="dash-low-list">
              {expenseRows.slice(0, 5).map((c) => (
                <div key={c.category_id ?? "uncat"} className="dash-low-row">
                  <span>{c.category_name}</span>
                  <span><XAFAmount value={c.total} withSuffix={false} /></span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      {/* Brokered-sale gains (§7B.1 / §7C.4) */}
      <div className="dash-card">
        <div className="dash-card-title">Brokered gains ({period})</div>
        {brokered.isLoading ? (
          <div className="dash-card-empty">Loading…</div>
        ) : (br?.line_count ?? 0) === 0 ? (
          <div className="dash-card-empty">No brokered sales this period.</div>
        ) : (
          <>
            <div className="dash-profit-big"><XAFAmount value={br.gain} /></div>
            <div className="dash-profit-sub">
              {br.line_count} item{br.line_count === 1 ? "" : "s"} · sold <XAFAmount value={br.revenue} />, sourced <XAFAmount value={br.cost} />
            </div>
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
