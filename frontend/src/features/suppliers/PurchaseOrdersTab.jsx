import { useMemo, useState } from "react";
import XAFAmount from "../../components/XAFAmount";
import { useInventoryProducts } from "../../hooks/useInventory";
import {
  useCreatePurchaseOrder,
  usePurchaseOrderTransition,
  useReceivePurchaseOrder,
} from "../../hooks/useSuppliers";

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}
function formatDate(isoDate) {
  if (!isoDate) return "—";
  return new Date(`${isoDate}T00:00:00`).toLocaleDateString("en-GB", {
    day: "2-digit", month: "short", year: "numeric",
  });
}

const STATUS_LABEL = {
  draft: "Draft",
  sent: "Sent",
  partially_received: "Partially received",
  received: "Received",
  cancelled: "Cancelled",
};

let poLineSeq = 0;
const emptyLine = () => ({ key: ++poLineSeq, product: "", quantity_ordered: "", unit_cost: "" });

// New-PO form: same line-builder shape as RecordPurchaseForm, but quantities
// are *ordered* and no stock moves. A PO can be saved as a draft or sent.
function NewPurchaseOrderForm({ supplier, onCancel, onSuccess, onError }) {
  const { data: products } = useInventoryProducts();
  const createPO = useCreatePurchaseOrder();
  const [orderDate, setOrderDate] = useState(todayIso());
  const [expectedDate, setExpectedDate] = useState("");
  const [lines, setLines] = useState(() => [emptyLine()]);

  const activeProducts = useMemo(() => (products ?? []).filter((p) => p.is_active), [products]);
  const update = (key, patch) => setLines((l) => l.map((x) => (x.key === key ? { ...x, ...patch } : x)));
  const complete = (l) => l.product && Number(l.quantity_ordered) > 0 && Number(l.unit_cost) >= 0;
  const completeLines = lines.filter(complete);
  const total = completeLines.reduce((s, l) => s + Number(l.quantity_ordered) * Number(l.unit_cost), 0);
  const canSubmit =
    completeLines.length > 0 && completeLines.length === lines.length && orderDate && !createPO.isPending;

  async function submit(status) {
    if (!canSubmit) return;
    try {
      await createPO.mutateAsync({
        supplier: supplier.id,
        order_date: orderDate,
        expected_date: expectedDate || undefined,
        status,
        items: completeLines.map((l) => ({
          product: l.product,
          quantity_ordered: Number(l.quantity_ordered),
          unit_cost: Number(l.unit_cost),
        })),
      });
      onSuccess(status === "sent" ? "Purchase order sent." : "Draft purchase order saved.");
    } catch (err) {
      onError(err, "Couldn’t create the purchase order.");
    }
  }

  return (
    <form className="po-form" onSubmit={(e) => e.preventDefault()}>
      <div className="po-form-row">
        <label className="po-field">
          <span className="po-field-label">Order date</span>
          <input type="date" className="po-input" value={orderDate} onChange={(e) => setOrderDate(e.target.value)} />
        </label>
        <label className="po-field">
          <span className="po-field-label">Expected (optional)</span>
          <input type="date" className="po-input" value={expectedDate} onChange={(e) => setExpectedDate(e.target.value)} />
        </label>
      </div>

      {lines.map((l) => (
        <div className="po-line" key={l.key}>
          <select className="po-input po-line-product" value={l.product} onChange={(e) => update(l.key, { product: e.target.value })}>
            <option value="">Select product…</option>
            {activeProducts.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
          <input className="po-input po-line-qty" type="number" min="1" placeholder="Qty" value={l.quantity_ordered} onChange={(e) => update(l.key, { quantity_ordered: e.target.value })} />
          <input className="po-input po-line-cost" type="number" min="0" placeholder="Unit cost" value={l.unit_cost} onChange={(e) => update(l.key, { unit_cost: e.target.value })} />
          <button type="button" className="po-line-remove" onClick={() => setLines((c) => (c.length > 1 ? c.filter((x) => x.key !== l.key) : c))}>×</button>
        </div>
      ))}
      <button type="button" className="po-add-line" onClick={() => setLines((c) => [...c, emptyLine()])}>+ Add line</button>

      <div className="po-form-footer">
        <span className="po-total">Total: <XAFAmount value={total} /></span>
        <div className="po-form-actions">
          <button type="button" className="sup-row-btn" onClick={onCancel}>Cancel</button>
          <button type="button" className="sup-row-btn" disabled={!canSubmit} onClick={() => submit("draft")}>Save draft</button>
          <button type="button" className="sup-hdr-btn" disabled={!canSubmit} onClick={() => submit("sent")}>Create + send</button>
        </div>
      </div>
    </form>
  );
}

// Inline receive form for one PO: a qty input per outstanding line (capped at
// what's left), optional payment.
function ReceiveForm({ po, onCancel, onSuccess, onError }) {
  const receive = useReceivePurchaseOrder();
  const outstandingLines = po.line_items.filter((l) => l.outstanding > 0);
  const [qty, setQty] = useState(() => Object.fromEntries(outstandingLines.map((l) => [l.id, ""])));
  const [amountPaid, setAmountPaid] = useState("");
  const [purchaseDate, setPurchaseDate] = useState(todayIso());

  const receipts = outstandingLines
    .map((l) => ({ line: l.id, quantity: Number(qty[l.id] || 0), max: l.outstanding }))
    .filter((r) => r.quantity > 0);
  const overCap = receipts.some((r) => r.quantity > r.max);
  const canSubmit = receipts.length > 0 && !overCap && !receive.isPending;

  async function submit() {
    if (!canSubmit) return;
    try {
      await receive.mutateAsync({
        id: po.id,
        payload: {
          receipts: receipts.map((r) => ({ line: r.line, quantity: r.quantity })),
          purchase_date: purchaseDate,
          amount_paid: amountPaid === "" ? 0 : Number(amountPaid),
        },
      });
      onSuccess("Goods received — stock updated.");
    } catch (err) {
      onError(err, "Couldn’t receive against this order.");
    }
  }

  return (
    <div className="po-receive">
      {outstandingLines.map((l) => (
        <div className="po-receive-line" key={l.id}>
          <span className="po-receive-name">{l.product_name}</span>
          <span className="po-receive-out">{l.outstanding} outstanding</span>
          <input
            className="po-input po-line-qty"
            type="number" min="0" max={l.outstanding} placeholder="0"
            value={qty[l.id]}
            onChange={(e) => setQty((q) => ({ ...q, [l.id]: e.target.value }))}
          />
        </div>
      ))}
      <div className="po-form-row">
        <label className="po-field">
          <span className="po-field-label">Received on</span>
          <input type="date" className="po-input" value={purchaseDate} onChange={(e) => setPurchaseDate(e.target.value)} />
        </label>
        <label className="po-field">
          <span className="po-field-label">Amount paid (optional)</span>
          <input type="number" min="0" className="po-input" placeholder="0" value={amountPaid} onChange={(e) => setAmountPaid(e.target.value)} />
        </label>
      </div>
      <div className="po-form-actions">
        <button type="button" className="sup-row-btn" onClick={onCancel}>Cancel</button>
        <button type="button" className="sup-hdr-btn" disabled={!canSubmit} onClick={submit}>Receive</button>
      </div>
    </div>
  );
}

export default function PurchaseOrdersTab({ supplier, purchaseOrders, onSuccess, onError }) {
  const [showNew, setShowNew] = useState(false);
  const [receivingId, setReceivingId] = useState(null);
  const transition = usePurchaseOrderTransition();

  async function doTransition(id, action) {
    try {
      await transition.mutateAsync({ id, action });
      onSuccess(action === "send" ? "Purchase order sent." : "Purchase order cancelled.");
    } catch (err) {
      onError(err, "Couldn’t update the purchase order.");
    }
  }

  return (
    <div className="po-tab">
      <div className="po-tab-head">
        <span className="po-tab-title">Purchase orders</span>
        <button
          type="button"
          className="sup-hdr-btn"
          disabled={!supplier.is_active}
          title={supplier.is_active ? undefined : "Reactivate this supplier to order."}
          onClick={() => { setShowNew((v) => !v); setReceivingId(null); }}
        >
          {showNew ? "Cancel" : "+ New order"}
        </button>
      </div>

      {showNew && (
        <NewPurchaseOrderForm
          supplier={supplier}
          onCancel={() => setShowNew(false)}
          onSuccess={(m) => { setShowNew(false); onSuccess(m); }}
          onError={onError}
        />
      )}

      {purchaseOrders.length === 0 && !showNew ? (
        <div className="po-empty">No purchase orders for this supplier yet.</div>
      ) : (
        <div className="po-list">
          {purchaseOrders.map((po) => {
            const ordered = po.line_items.reduce((s, l) => s + l.quantity_ordered, 0);
            const received = po.line_items.reduce((s, l) => s + l.quantity_received, 0);
            const open = ["draft", "sent", "partially_received"].includes(po.status);
            return (
              <div className="po-card" key={po.id}>
                <div className="po-card-head">
                  <span className={`po-status po-status-${po.status}`}>{STATUS_LABEL[po.status] ?? po.status}</span>
                  <span className="po-card-date">Ordered {formatDate(po.order_date)}</span>
                  {po.expected_date && <span className="po-card-date">· expected {formatDate(po.expected_date)}</span>}
                  <span className="po-card-total"><XAFAmount value={po.total_ordered_amount} /></span>
                </div>
                <div className="po-card-progress">{received} / {ordered} units received</div>

                <div className="po-card-actions">
                  {po.status === "draft" && (
                    <button type="button" className="sup-row-btn" onClick={() => doTransition(po.id, "send")}>Send</button>
                  )}
                  {(po.status === "sent" || po.status === "partially_received") && (
                    <button
                      type="button"
                      className="sup-row-btn"
                      onClick={() => setReceivingId(receivingId === po.id ? null : po.id)}
                    >
                      {receivingId === po.id ? "Close" : "Receive"}
                    </button>
                  )}
                  {open && (
                    <button type="button" className="sup-row-btn" onClick={() => doTransition(po.id, "cancel")}>Cancel order</button>
                  )}
                </div>

                {receivingId === po.id && (
                  <ReceiveForm
                    po={po}
                    onCancel={() => setReceivingId(null)}
                    onSuccess={(m) => { setReceivingId(null); onSuccess(m); }}
                    onError={onError}
                  />
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
