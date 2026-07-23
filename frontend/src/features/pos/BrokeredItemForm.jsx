import { useState } from "react";
import XAFAmount from "../../components/XAFAmount";

// "Sell as sourced" form (Phase 2 §7B.1). Opened when a cashier taps an
// out-of-stock product: the shop doesn't have it but will source it from
// an outside seller and sell at a markup. We capture what will be paid
// to the source (external cost) and an optional note of who it's sourced
// from; the item sells at its catalogue price and moves no stock.
//
// Rendered as an overlay confined to the POS right panel (its parent is
// position: relative), same convention as InlineConfirm.
export default function BrokeredItemForm({ product, onCancel, onConfirm }) {
  const [quantity, setQuantity] = useState(1);
  const [externalCost, setExternalCost] = useState("");
  const [sourceNote, setSourceNote] = useState("");

  const cost = Number(externalCost);
  const qty = Number(quantity);
  const price = product.effective_retail_price;
  const validCost = externalCost !== "" && cost >= 0;
  const validQty = Number.isInteger(qty) && qty >= 1;
  const canAdd = validCost && validQty;

  // Live gain preview so the cashier sees the margin before adding.
  const gainPerUnit = validCost ? price - cost : null;

  return (
    <div className="inline-confirm-backdrop">
      <div className="inline-confirm">
        <p className="inline-confirm-title">Sell sourced item</p>
        <p className="inline-confirm-sub">
          {product.name} — not in stock. Sells at <XAFAmount value={price} /> each.
        </p>

        <label className="pos-brokered-label" htmlFor="brk-qty">Quantity</label>
        <input
          id="brk-qty"
          type="number"
          min="1"
          className="inline-confirm-input"
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
        />

        <label className="pos-brokered-label" htmlFor="brk-cost">What you'll pay the source (per unit, XAF)</label>
        <input
          id="brk-cost"
          type="number"
          min="0"
          className="inline-confirm-input"
          placeholder="e.g. 8000"
          value={externalCost}
          onChange={(e) => setExternalCost(e.target.value)}
          autoFocus
        />

        <label className="pos-brokered-label" htmlFor="brk-note">Sourced from (optional)</label>
        <input
          id="brk-note"
          type="text"
          className="inline-confirm-input"
          placeholder="e.g. Neighbour Eric"
          value={sourceNote}
          onChange={(e) => setSourceNote(e.target.value)}
        />

        {gainPerUnit !== null && (
          <p className={`pos-brokered-gain${gainPerUnit < 0 ? " loss" : ""}`}>
            {gainPerUnit < 0 ? "Loss" : "Gain"} per unit: <XAFAmount value={Math.abs(gainPerUnit)} />
          </p>
        )}

        <div className="inline-confirm-actions">
          <button type="button" className="inline-confirm-cancel-btn" onClick={onCancel}>
            Cancel
          </button>
          <button
            type="button"
            className="inline-confirm-btn"
            disabled={!canAdd}
            onClick={() => onConfirm({ quantity: qty, externalCost: cost, sourceNote: sourceNote.trim() })}
          >
            Add to sale
          </button>
        </div>
      </div>
    </div>
  );
}
