import XAFAmount from "../../components/XAFAmount";

// "Ranked list, revenue-sorted, shows units sold + revenue per
// product" (UI Design Reference Screen 5). TopProductsView already
// returns rows pre-ranked/sorted server-side (order_by("-revenue") +
// enumerate()), so this component only renders -- no client-side
// sorting.
export default function TopProductsTable({ products, isLoading }) {
  return (
    <div className="dash-card">
      <div className="dash-card-title">Top products</div>

      {isLoading ? (
        <div className="dash-empty">Loading…</div>
      ) : !products || products.length === 0 ? (
        <div className="dash-empty">No sales in this period.</div>
      ) : (
        <table className="dash-top-products-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Product</th>
              <th>Units</th>
              <th>Revenue</th>
            </tr>
          </thead>
          <tbody>
            {products.map((p) => (
              <tr key={p.product_id}>
                <td className="dash-tp-rank">{p.rank}</td>
                <td>{p.product_name}</td>
                <td>{p.units_sold}</td>
                <td className="dash-tp-revenue">
                  <XAFAmount value={p.revenue} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
