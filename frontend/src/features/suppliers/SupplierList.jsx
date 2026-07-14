import XAFAmount from "../../components/XAFAmount";

// purchase_count / total_spent come straight from SupplierViewSet's
// queryset annotations (see api/suppliers.js) -- no client-side
// aggregation needed here, unlike the unpaid/partial count shown in
// SupplierDetail's stats strip, which isn't annotated server-side.
export default function SupplierList({
  suppliers,
  search,
  onSearchChange,
  selectedId,
  onSelect,
  onAddSupplier,
  isLoading,
}) {
  return (
    <div className="sup-list-panel">
      <div className="sup-list-header">
        <input
          className="sup-search"
          placeholder="Search suppliers…"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
        />
      </div>

      <div className="sup-list-scroll">
        {isLoading ? (
          <div className="sup-list-empty">Loading…</div>
        ) : suppliers.length === 0 ? (
          <div className="sup-list-empty">
            {search ? "No suppliers match your search." : "No suppliers yet."}
          </div>
        ) : (
          suppliers.map((s) => (
            <div
              key={s.id}
              className={`sup-item${selectedId === s.id ? " active" : ""}${s.is_active ? "" : " inactive"}`}
              onClick={() => onSelect(s.id)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") onSelect(s.id);
              }}
            >
              <div className="sup-item-name">
                {s.name}
                {!s.is_active && <span className="sup-item-inactive-tag">Inactive</span>}
              </div>
              <div className="sup-item-meta">
                {s.area ? `📍 ${s.area}` : "No area set"}
                {s.phone ? ` · ${s.phone}` : ""}
              </div>
              <div className="sup-item-total">
                {s.purchase_count} purchase{s.purchase_count === 1 ? "" : "s"} ·{" "}
                <XAFAmount value={s.total_spent} /> total
              </div>
            </div>
          ))
        )}
      </div>

      <div className="sup-list-footer">
        <button type="button" className="sup-add-supplier-btn" onClick={onAddSupplier}>
          + Add supplier
        </button>
      </div>
    </div>
  );
}
