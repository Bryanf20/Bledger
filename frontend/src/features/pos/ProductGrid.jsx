import XAFAmount from "../../components/XAFAmount";

export default function ProductGrid({ products, onSelect, onBrokered, view }) {
  if (!products.length) {
    return <div className="pos-empty-state">No products match your search.</div>;
  }

  return (
    <div className={`pos-prod-grid${view === "list" ? " list" : ""}`}>
      {products.map((p) => {
        const outOfStock = p.stock_level <= 0;
        return (
          <button
            key={p.id}
            type="button"
            className={`pos-prod-card${outOfStock ? " out" : ""}`}
            // Out-of-stock products aren't dead — tapping one starts a
            // brokered (sourced) sale (Phase 2 §7B.1) instead of adding
            // to the cart normally.
            onClick={() => (outOfStock ? onBrokered?.(p) : onSelect(p))}
          >
            <div className="pos-prod-name">{p.name}</div>
            <div className="pos-prod-price">
              <XAFAmount value={p.effective_retail_price} />
            </div>
            {p.effective_bulk_price != null && p.bulk_min_qty != null && (
              <div className="pos-prod-bulk">
                Bulk: <XAFAmount value={p.effective_bulk_price} /> ×{p.bulk_min_qty}
              </div>
            )}
            <div className={`pos-prod-stock${outOfStock ? " danger" : p.stock_status === "low" ? " warning" : ""}`}>
              {outOfStock ? "Out — tap to sell sourced" : `Stock: ${p.stock_level}${p.stock_status === "low" ? " ⚠" : ""}`}
            </div>
          </button>
        );
      })}
    </div>
  );
}
