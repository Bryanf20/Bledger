import { useMemo, useState } from "react";
import XAFAmount from "../../components/XAFAmount";
import { useInventoryProducts } from "../../hooks/useInventory";
import { useCreatePurchase } from "../../hooks/useSuppliers";

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

let lineKeySeq = 0;
function emptyLine() {
  return { key: ++lineKeySeq, product: "", quantity: "", unit_cost: "" };
}

// [DEVIATION -- FLAGGED] Two places this form deliberately departs
// from the UI Design Reference's "Record purchase form" description,
// both caught by checking backend/apps/suppliers/{models,serializers}.py
// in project knowledge before building rather than implementing the
// doc text directly:
//
//  1. The doc lists an "optional note" field. Purchase has no
//     note/notes column at all (Supplier does, but that's a
//     different model/field) -- omitted rather than added
//     speculatively; would need its own migration to support.
//
//  2. The doc lists a "payment status selector". PurchaseSerializer
//     marks payment_status read_only and always derives it
//     server-side from amount_paid vs the computed total (see
//     PurchaseSerializer.create()) -- paid/partial/credit is never
//     client-supplied. This form only collects amount_paid and shows
//     a live preview of the status the server will assign, via the
//     same badge component the history table uses.
export default function RecordPurchaseForm({ supplier, onCancel, onSuccess, onError }) {
  const { data: products } = useInventoryProducts();
  const createPurchase = useCreatePurchase();

  const [purchaseDate, setPurchaseDate] = useState(todayIso());
  const [amountPaid, setAmountPaid] = useState("");
  const [lines, setLines] = useState(() => [emptyLine()]);

  const activeProducts = useMemo(() => (products ?? []).filter((p) => p.is_active), [products]);

  function updateLine(key, patch) {
    setLines((current) => current.map((l) => (l.key === key ? { ...l, ...patch } : l)));
  }
  function addLine() {
    setLines((current) => [...current, emptyLine()]);
  }
  function removeLine(key) {
    setLines((current) => (current.length > 1 ? current.filter((l) => l.key !== key) : current));
  }

  const isLineComplete = (l) => l.product && Number(l.quantity) > 0 && Number(l.unit_cost) >= 0;
  const completeLines = lines.filter(isLineComplete);
  const total = completeLines.reduce((sum, l) => sum + Number(l.quantity) * Number(l.unit_cost), 0);
  const paid = amountPaid === "" ? 0 : Number(amountPaid);

  const previewStatus = total <= 0 ? null : paid <= 0 ? "credit" : paid < total ? "partial" : "paid";

  // Every row present must be complete -- a half-filled row is
  // treated as "not ready" rather than silently dropped on submit,
  // so the person notices and either finishes or removes it.
  const canSubmit =
    completeLines.length > 0 &&
    completeLines.length === lines.length &&
    Boolean(purchaseDate) &&
    paid >= 0 &&
    !createPurchase.isPending;

  async function handleSubmit(e) {
    e.preventDefault();
    if (!canSubmit) return;
    try {
      await createPurchase.mutateAsync({
        supplier: supplier.id,
        purchase_date: purchaseDate,
        amount_paid: paid,
        items: completeLines.map((l) => ({
          product: l.product,
          quantity: Number(l.quantity),
          unit_cost: Number(l.unit_cost),
        })),
      });
      onSuccess(`Purchase recorded for ${supplier.name}.`);
    } catch (err) {
      onError(err, "Couldn't record that purchase.");
    }
  }

  return (
    <form className="sup-purchase-form" onSubmit={handleSubmit}>
      <div className="sup-purchase-form-header">Record purchase — {supplier.name}</div>

      <div className="sup-line-items">
        <div className="sup-line-row sup-line-row-labels">
          <span>Product</span>
          <span>Qty</span>
          <span>Unit cost</span>
          <span>Line total</span>
          <span />
        </div>
        {lines.map((line) => (
          <div key={line.key} className="sup-line-row">
            <select
              className="sup-field-input"
              value={line.product}
              onChange={(e) => updateLine(line.key, { product: e.target.value })}
            >
              <option value="">Select product…</option>
              {activeProducts.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
            <input
              type="number"
              min="1"
              className="sup-field-input sup-line-qty"
              value={line.quantity}
              onChange={(e) => updateLine(line.key, { quantity: e.target.value })}
            />
            <input
              type="number"
              min="0"
              className="sup-field-input sup-line-cost"
              value={line.unit_cost}
              onChange={(e) => updateLine(line.key, { unit_cost: e.target.value })}
            />
            <div className="sup-line-total">
              {isLineComplete(line) ? (
                <XAFAmount value={Number(line.quantity) * Number(line.unit_cost)} />
              ) : (
                <span className="sup-muted">—</span>
              )}
            </div>
            <button
              type="button"
              className="sup-icon-btn"
              onClick={() => removeLine(line.key)}
              disabled={lines.length === 1}
              aria-label="Remove line"
              title="Remove line"
            >
              ×
            </button>
          </div>
        ))}
        <button type="button" className="sup-add-line-btn" onClick={addLine}>+ Add line</button>
      </div>

      <div className="sup-purchase-form-row">
        <div>
          <label className="sup-field-label" htmlFor="purchase_date">Purchase date</label>
          <input
            id="purchase_date"
            type="date"
            className="sup-field-input"
            value={purchaseDate}
            onChange={(e) => setPurchaseDate(e.target.value)}
          />
        </div>
        <div>
          <label className="sup-field-label" htmlFor="amount_paid">Amount paid</label>
          <input
            id="amount_paid"
            type="number"
            min="0"
            className="sup-field-input"
            placeholder="0"
            value={amountPaid}
            onChange={(e) => setAmountPaid(e.target.value)}
          />
        </div>
      </div>

      <div className="sup-purchase-form-summary">
        <span className="sup-purchase-form-total">
          Total: <XAFAmount value={total} />
        </span>
        {previewStatus && (
          <span className={`sup-badge sup-badge-${previewStatus === "paid" ? "success" : previewStatus === "partial" ? "warning" : "danger"}`}>
            Will be marked {previewStatus === "paid" ? "Paid" : previewStatus === "partial" ? "Partial" : "Credit"}
          </span>
        )}
      </div>

      <div className="sup-purchase-form-actions">
        <button type="button" className="sup-row-btn" onClick={onCancel}>Cancel</button>
        <button type="submit" className="sup-confirm-btn" disabled={!canSubmit}>
          {createPurchase.isPending ? "Recording…" : "Record purchase"}
        </button>
      </div>
    </form>
  );
}
