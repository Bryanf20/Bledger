import { useState } from "react";
import { useCreateStockAdjustment } from "../../hooks/useInventory";
import "./InventoryScreen.css";

const TYPES = [
  { key: "add", label: "Add (restock)" },
  { key: "remove", label: "Remove (damage/expiry)" },
  { key: "correction", label: "Correction (count discrepancy)" },
];

export default function AdjustStockPanel({ product, onClose, onSuccess, onError }) {
  const [type, setType] = useState("add");
  const [amount, setAmount] = useState("");
  const [direction, setDirection] = useState("increase"); // correction only
  const [reason, setReason] = useState("");
  const createAdjustment = useCreateStockAdjustment();

  const parsedAmount = Number(amount);
  const isValidAmount = amount !== "" && Number.isFinite(parsedAmount) && parsedAmount > 0;

  function signedQuantity() {
    if (type === "remove") return -parsedAmount;
    if (type === "correction" && direction === "decrease") return -parsedAmount;
    return parsedAmount;
  }

  const previewStock = isValidAmount ? product.stock_level + signedQuantity() : product.stock_level;
  const canSubmit = isValidAmount && reason.trim().length > 0 && !createAdjustment.isPending;

  async function handleSubmit(e) {
    e.preventDefault();
    if (!canSubmit) return;
    try {
      await createAdjustment.mutateAsync({
        product: product.id,
        adjustment_type: type,
        quantity: signedQuantity(),
        reason: reason.trim(),
      });
      onSuccess(`Stock adjusted for ${product.name}.`);
    } catch (err) {
      onError(err, "Couldn't record that stock adjustment.");
    }
  }

  return (
    <div className="inv-drawer-backdrop" onClick={onClose}>
      <div className="inv-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="inv-drawer-header">
          <span>Adjust stock — {product.name}</span>
          <button type="button" className="inv-icon-btn" onClick={onClose}>Close</button>
        </div>

        <form className="inv-form" onSubmit={handleSubmit}>
          <div className="inv-form-scroll">
            <div className="inv-current-stock">Current stock: {product.stock_level} {product.unit}</div>

            <div>
              <label className="inv-field-label">Adjustment type</label>
              <div className="inv-type-row">
                {TYPES.map((t) => (
                  <button key={t.key} type="button" className={`inv-type-btn${type === t.key ? " active" : ""}`} onClick={() => setType(t.key)}>
                    {t.label}
                  </button>
                ))}
              </div>
            </div>

            {type === "correction" && (
              <div>
                <label className="inv-field-label">Direction</label>
                <div className="inv-type-row">
                  <button type="button" className={`inv-type-btn${direction === "increase" ? " active" : ""}`} onClick={() => setDirection("increase")}>
                    Increase
                  </button>
                  <button type="button" className={`inv-type-btn${direction === "decrease" ? " active" : ""}`} onClick={() => setDirection("decrease")}>
                    Decrease
                  </button>
                </div>
              </div>
            )}

            <div>
              <label className="inv-field-label" htmlFor="amount">Quantity</label>
              <input id="amount" type="number" min="1" className="inv-field-input" value={amount} onChange={(e) => setAmount(e.target.value)} />
            </div>

            {isValidAmount && (
              <div className="inv-info-note">
                New stock level will be <strong>{previewStock}</strong> {product.unit}.
                {previewStock < 0 && " This takes stock below zero — double-check the quantity."}
              </div>
            )}

            <div>
              <label className="inv-field-label" htmlFor="reason">Reason</label>
              <input id="reason" className="inv-field-input" placeholder="Required — e.g. 'Restock from supplier'" value={reason} onChange={(e) => setReason(e.target.value)} />
            </div>
          </div>

          <div className="inv-drawer-footer">
            <button type="button" className="inv-row-btn" onClick={onClose}>Cancel</button>
            <button type="submit" className="inv-confirm-btn" disabled={!canSubmit}>
              {createAdjustment.isPending ? "Recording…" : "Record adjustment"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
