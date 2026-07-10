import XAFAmount from "../../components/XAFAmount";

// [DEVIATION FROM MOCKUP -- INTENTIONAL, per the UI Design Reference]
// Plain CSS horizontal bars, no charting library -- "to keep the
// bundle small for low-spec hardware... preserve this approach rather
// than introducing a chart dependency." Bucket granularity (hourly
// for "today", daily for week/month) is entirely server-side
// (SalesChartView's TruncHour/TruncDay) -- this component just renders
// whatever {label, revenue} points it's given.
export default function SalesChart({ data, isLoading }) {
  if (isLoading) {
    return (
      <div className="dash-card">
        <div className="dash-card-title">Sales</div>
        <div className="dash-empty">Loading chart…</div>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="dash-card">
        <div className="dash-card-title">Sales</div>
        <div className="dash-empty">No sales in this period.</div>
      </div>
    );
  }

  const max = Math.max(1, ...data.map((point) => point.revenue));

  return (
    <div className="dash-card">
      <div className="dash-card-title">Sales</div>
      <div className="dash-chart">
        {data.map((point, i) => (
          <div className="dash-chart-row" key={`${point.label}-${i}`}>
            <span className="dash-chart-label">{point.label}</span>
            <div className="dash-chart-bar-track">
              <div className="dash-chart-bar" style={{ width: `${(point.revenue / max) * 100}%` }} />
            </div>
            <span className="dash-chart-value">
              <XAFAmount value={point.revenue} withSuffix={false} />
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
