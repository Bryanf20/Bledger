import XAFAmount from "../../components/XAFAmount";

function stockBadgeText(p) {
  if (p.stock_status === "out") return "Out of stock";
  if (p.stock_status === "low") return `Low — ${p.stock_level} left`;
  return `${p.stock_level} units`;
}

export default function ProductCard({ product: p, canEdit, onEdit, onAdjust, onReactivate }) {
  return (
    <div className={`inv-card${!p.is_active ? " inactive" : ""}`}>
      <div className="inv-card-top">
        <div className="inv-card-name">{p.name}</div>
        {!p.is_active && <span className="inv-inactive-badge">Deactivated</span>}
      </div>
      <div className="inv-card-cat">{p.category_name}</div>
      {p.description && <div className="inv-card-desc">{p.description}</div>}
      <div className="inv-card-price">
        <XAFAmount value={p.effective_retail_price} /> / {p.unit}
      </div>
      {p.effective_bulk_price != null && p.bulk_min_qty != null && (
        <span className="inv-bulk-badge">
          Bulk <XAFAmount value={p.effective_bulk_price} /> ×{p.bulk_min_qty}
        </span>
      )}
      <div className={`inv-stock-badge inv-stock-${p.stock_status}`}>{stockBadgeText(p)}</div>

      {canEdit && (
        <div className="inv-card-actions">
          {p.is_active ? (
            <>
              <button type="button" className="inv-row-btn" onClick={() => onAdjust(p)}>Adjust</button>
              <button type="button" className="inv-row-btn" onClick={() => onEdit(p)}>Edit</button>
            </>
          ) : (
            <button type="button" className="inv-row-btn" onClick={() => onReactivate(p)}>Reactivate</button>
          )}
        </div>
      )}
    </div>
  );
}
