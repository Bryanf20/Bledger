import { useState } from "react";
import XAFAmount from "../../components/XAFAmount";
import { useRecordPurchasePayment } from "../../hooks/useSuppliers";

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

// Embedded inside PurchaseDetailPanel now (added this session), not a
// standalone below-the-table form anymore -- there's no "open/close
// toggle" state to cancel out of once it lives inside an always-open
// detail view, so "Cancel" became "Clear" (resets the three fields,
// nothing more) and there's no onCancel prop to wire up. Reuses
// RecordPurchaseForm's established sup-field-label/sup-field-input/
// sup-purchase-form-row/sup-purchase-form-summary/sup-purchase-form-
// actions/sup-row-btn/sup-confirm-btn/sup-badge classes -- only the
// header bar (sup-payment-form-header/-balance) is new to this form.
export default function RecordPaymentForm({ purchase, onSuccess, onError }) {
  const recordPayment = useRecordPurchasePayment();

  const [amount, setAmount] = useState("");
  const [paymentDate, setPaymentDate] = useState(todayIso());
  const [note, setNote] = useState("");

  function resetFields() {
    setAmount("");
    setPaymentDate(todayIso());
    setNote("");
  }

  const amountNum = amount === "" ? 0 : Number(amount);
  const isValidAmount = amountNum > 0 && amountNum <= purchase.balance_due;
  const remainingAfter = purchase.balance_due - amountNum;
  const previewStatus = !isValidAmount ? null : remainingAfter <= 0 ? "paid" : "partial";

  async function handleSubmit(e) {
    e.preventDefault();
    if (!isValidAmount) return;
    try {
      const updated = await recordPayment.mutateAsync({
        purchaseId: purchase.id,
        payload: { amount: amountNum, payment_date: paymentDate, note: note.trim() },
      });
      resetFields();
      onSuccess(
        updated.payment_status === "paid"
          ? "Payment recorded — purchase fully paid."
          : `Payment recorded. ${updated.balance_due} XAF still owed.`,
      );
    } catch (err) {
      onError(err, "Couldn't record that payment.");
    }
  }

  return (
    <form className="sup-payment-form" onSubmit={handleSubmit}>
      <div className="sup-payment-form-header">
        <span>Record payment</span>
        <span className="sup-payment-form-balance">
          Balance due: <XAFAmount value={purchase.balance_due} />
        </span>
      </div>

      <div className="sup-purchase-form-row">
        <div>
          <label className="sup-field-label" htmlFor="payment-amount">Amount</label>
          <input
            id="payment-amount"
            type="number"
            min="1"
            max={purchase.balance_due}
            className="sup-field-input"
            placeholder="0"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
          />
        </div>
        <div>
          <label className="sup-field-label" htmlFor="payment-date">Date</label>
          <input
            id="payment-date"
            type="date"
            className="sup-field-input"
            value={paymentDate}
            onChange={(e) => setPaymentDate(e.target.value)}
          />
        </div>
      </div>

      <div>
        <label className="sup-field-label" htmlFor="payment-note">Note <span className="sup-field-hint">(optional)</span></label>
        <input
          id="payment-note"
          type="text"
          className="sup-field-input"
          placeholder="e.g. Paid via MTN MoMo"
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
      </div>

      <div className="sup-purchase-form-summary">
        <span className="sup-purchase-form-total">
          Remaining after this payment: <XAFAmount value={Math.max(remainingAfter, 0)} />
        </span>
        {previewStatus && (
          <span className={`sup-badge sup-badge-${previewStatus === "paid" ? "success" : "warning"}`}>
            Will be marked {previewStatus === "paid" ? "Paid" : "Partial"}
          </span>
        )}
      </div>

      <div className="sup-purchase-form-actions">
        <button type="button" className="sup-row-btn" onClick={resetFields}>Clear</button>
        <button type="submit" className="sup-confirm-btn" disabled={!isValidAmount || recordPayment.isPending}>
          {recordPayment.isPending ? "Recording…" : "Record payment"}
        </button>
      </div>
    </form>
  );
}
