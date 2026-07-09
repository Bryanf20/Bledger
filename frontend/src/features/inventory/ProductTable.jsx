import XAFAmount from "../../components/XAFAmount";

function stockBadgeText(p) {
  if (p.stock_status === "out") return "Out of stock";
  if (p.stock_status === "low") return `Low — ${p.stock_level} left`;
  return `${p.stock_level} units`;
}

export default function ProductTable({ products, canEdit, onEdit, onAdjust, onReactivate }) {
  if (!products.length) {
    return <div className="inv-empty-state">No products match your search.</div>;
  }

  return (
    <table className="inv-table">
      <thead>
        <tr>
          <th>Product</th>
          <th>Category</th>
          <th>Unit</th>
          <th>Retail price</th>
          <th>Bulk price</th>
          <th>Stock</th>
          {canEdit && <th>Actions</th>}
        </tr>
      </thead>
      <tbody>
        {products.map((p) => (
          <tr key={p.id} className={!p.is_active ? "inv-row-inactive" : ""}>
            <td className="inv-cell-name">
              <div className="inv-cell-name-inner">
                {p.name}
                {!p.is_active && <span className="inv-inactive-badge">Deactivated</span>}
              </div>
            </td>
            <td>{p.category_name}</td>
            <td>{p.unit}</td>
            <td><XAFAmount value={p.effective_retail_price} /></td>
            <td>
              {p.effective_bulk_price != null && p.bulk_min_qty != null ? (
                <span className="inv-bulk-badge">
                  <XAFAmount value={p.effective_bulk_price} /> ×{p.bulk_min_qty}
                </span>
              ) : (
                <span className="inv-muted">—</span>
              )}
            </td>
            <td>
              <span className={`inv-stock-text inv-stock-${p.stock_status}`}>{stockBadgeText(p)}</span>
            </td>
            {canEdit && (
              <td className="inv-actions-cell">
                <div className="inv-actions-inner">
                  {p.is_active ? (
                    <>
                      <button type="button" className="inv-row-btn" onClick={() => onAdjust(p)}>Adjust</button>
                      <button type="button" className="inv-row-btn" onClick={() => onEdit(p)}>Edit</button>
                    </>
                  ) : (
                    <button type="button" className="inv-row-btn" onClick={() => onReactivate(p)}>Reactivate</button>
                  )}
                </div>
              </td>
            )}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
