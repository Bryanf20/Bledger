const METHODS = [
  { value: "cash", label: "💵 Cash" },
  { value: "mtn_momo", label: "📱 MTN MoMo" },
  { value: "orange_money", label: "📱 Orange Money" },
  { value: "credit", label: "📓 Credit" },
  { value: "other", label: "⋯ Other" },
];

export default function PaymentPanel({
  method,
  onMethodChange,
  momoReference,
  onMomoReferenceChange,
  momoConfirmed,
  onMomoConfirmedChange,
  // Credit-sale props (Phase 2 §4): the selected customer + balance, and
  // the customer picker to open. Rendered only when method === "credit".
  customer,
  onPickCustomer,
  upfront,
  onUpfrontChange,
}) {
  const isMomo = method === "mtn_momo" || method === "orange_money";
  const isCredit = method === "credit";

  return (
    <div>
      <p className="pos-panel-label">Payment method</p>
      <div className="pos-pay-methods">
        {METHODS.map((m) => (
          <button
            key={m.value}
            type="button"
            className={`pos-pay-btn${method === m.value ? " sel" : ""}`}
            onClick={() => onMethodChange(m.value)}
          >
            {m.label}
          </button>
        ))}
      </div>

      {isMomo && (
        <div className="pos-momo-panel">
          <p className="pos-momo-label">📱 Mobile Money details</p>
          <input
            className="pos-momo-input"
            placeholder="Transaction reference"
            value={momoReference}
            onChange={(e) => onMomoReferenceChange(e.target.value)}
          />
          <label className="pos-momo-check">
            <input
              type="checkbox"
              checked={momoConfirmed}
              onChange={(e) => onMomoConfirmedChange(e.target.checked)}
            />
            Payment confirmed on phone
          </label>
        </div>
      )}

      {isCredit && (
        <div className="pos-momo-panel">
          <p className="pos-momo-label">📓 Credit sale — who owes?</p>
          <button type="button" className="pos-icon-btn" onClick={onPickCustomer}>
            {customer ? `👤 ${customer.name}` : "Choose customer…"}
          </button>
          {customer && (
            <p className="pos-credit-balance">
              Owes now: {new Intl.NumberFormat("en-US").format(customer.balance)} XAF · Limit:{" "}
              {new Intl.NumberFormat("en-US").format(customer.credit_limit)} XAF
            </p>
          )}
          <label className="pos-momo-label" htmlFor="pos-upfront">Paid now (optional)</label>
          <input
            id="pos-upfront"
            type="number"
            min="0"
            className="pos-momo-input"
            placeholder="Cash paid upfront, if any"
            value={upfront}
            onChange={(e) => onUpfrontChange(e.target.value)}
          />
        </div>
      )}
    </div>
  );
}
