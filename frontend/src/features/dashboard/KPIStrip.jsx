import XAFAmount from "../../components/XAFAmount";

// Design doc B.5 / UI Design Reference Screen 5: "revenue,
// transactions, average sale value, top product -- four columns, each
// with a period-over-period comparison sub-label (e.g. '+12% vs
// yesterday')."
//
// DashboardSummarySerializer only carries a delta for revenue
// (revenue_change_pct) and transactions (transaction_count_change) --
// average_sale and top_product_name have no period-over-period figure
// server-side. [DEVIATION -- FLAGGED, not in the doc] rather than
// fabricate a delta for those two client-side, they render as plain
// values with no comparison sub-label; the doc's "+12%" example is
// followed exactly where the backend actually provides it.
const PERIOD_COMPARISON_LABEL = {
  today: "vs yesterday",
  week: "vs last week",
  month: "vs last month",
};

function DeltaLabel({ value, suffix, comparisonLabel }) {
  if (value === null || value === undefined) {
    return <span className="dash-kpi-delta neutral">No data for {comparisonLabel}</span>;
  }
  const positive = value >= 0;
  return (
    <span className={`dash-kpi-delta ${positive ? "positive" : "negative"}`}>
      {positive ? "+" : ""}
      {value}
      {suffix} {comparisonLabel}
    </span>
  );
}

export default function KPIStrip({ summary, period, isLoading }) {
  const comparisonLabel = PERIOD_COMPARISON_LABEL[period] ?? "vs previous period";

  if (isLoading || !summary) {
    return (
      <div className="dash-kpi-strip">
        {["Revenue", "Transactions", "Average sale", "Top product"].map((label) => (
          <div className="dash-kpi" key={label}>
            <div className="dash-kpi-label">{label}</div>
            <div className="dash-kpi-value dash-kpi-loading">—</div>
          </div>
        ))}
      </div>
    );
  }

  const revenuePct =
    summary.revenue_change_pct === null || summary.revenue_change_pct === undefined
      ? null
      : Math.round(summary.revenue_change_pct * 10) / 10;

  return (
    <div className="dash-kpi-strip">
      <div className="dash-kpi">
        <div className="dash-kpi-label">Revenue</div>
        <div className="dash-kpi-value">
          <XAFAmount value={summary.revenue} />
        </div>
        <DeltaLabel value={revenuePct} suffix="%" comparisonLabel={comparisonLabel} />
      </div>

      <div className="dash-kpi">
        <div className="dash-kpi-label">Transactions</div>
        <div className="dash-kpi-value">{summary.transaction_count}</div>
        <DeltaLabel value={summary.transaction_count_change} suffix="" comparisonLabel={comparisonLabel} />
      </div>

      <div className="dash-kpi">
        <div className="dash-kpi-label">Average sale</div>
        <div className="dash-kpi-value">
          <XAFAmount value={summary.average_sale} />
        </div>
      </div>

      <div className="dash-kpi">
        <div className="dash-kpi-label">Top product</div>
        <div className="dash-kpi-value dash-kpi-value-text">{summary.top_product_name ?? "—"}</div>
      </div>
    </div>
  );
}
