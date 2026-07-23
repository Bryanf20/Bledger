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
  // Damage/expiry loss booking (§7C.2 / step 8d): when removing stock and
  // the product has a known cost, offer to book the value lost as a
  // Losses/Damage expense. Confirmed (and editable) per the "ask each
  // time" decision, defaulting to |qty| × average_cost.
  const [bookExpense, setBookExpense] = useState(true);
  const [expenseAmount, setExpenseAmount] = useState("");
  const [expenseEdited, setExpenseEdited] = useState(false);
  const createAdjustment = useCreateStockAdjustment();

  const parsedAmount = Number(amount);
  const isValidAmount = amount !== "" && Number.isFinite(parsedAmount) && parsedAmount > 0;

  const hasCost = Boolean(product.cost_is_set) && (product.average_cost || 0) > 0;
  const showLossBooking = type === "remove" && hasCost;
  const defaultLoss = isValidAmount ? parsedAmount * (product.average_cost || 0) : 0;
  const effectiveLoss = expenseEdited ? Number(expenseAmount) || 0 : defaultLoss;

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
    const payload = {
      product: product.id,
      adjustment_type: type,
      quantity: signedQuantity(),
      reason: reason.trim(),
    };
    if (showLossBooking && bookExpense) {
      payload.book_as_expense = true;
      payload.expense_amount = effectiveLoss;
    }
    try {
      const result = await createAdjustment.mutateAsync(payload);
      const booked = result?.booked_expense_amount;
      onSuccess(
        booked
          ? `Stock adjusted for ${product.name}; ${booked.toLocaleString()} XAF booked as a loss.`
          : `Stock adjusted for ${product.name}.`,
      );
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

            {showLossBooking && (
              <div className="inv-loss-box">
                <label className="inv-loss-check">
                  <input type="checkbox" checked={bookExpense} onChange={(e) => setBookExpense(e.target.checked)} />
                  Book this loss as a Losses/Damage expense
                </label>
                {bookExpense && (
                  <div className="inv-loss-amount">
                    <label className="inv-field-label" htmlFor="loss">Loss amount (XAF)</label>
                    <input
                      id="loss"
                      type="number"
                      min="0"
                      className="inv-field-input"
                      value={expenseEdited ? expenseAmount : String(defaultLoss)}
                      onChange={(e) => { setExpenseEdited(true); setExpenseAmount(e.target.value); }}
                    />
                    <small className="inv-loss-hint">
                      Default is {parsedAmount || 0} × {(product.average_cost || 0).toLocaleString()} XAF cost. Edit if the true loss differs.
                    </small>
                  </div>
                )}
              </div>
            )}
            {type === "remove" && !hasCost && isValidAmount && (
              <div className="inv-info-note">
                No cost is recorded for this product, so no loss can be booked. Set a cost via a purchase to track damage value.
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
