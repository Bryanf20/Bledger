const METHODS = [
  { value: "cash", label: "💵 Cash" },
  { value: "mtn_momo", label: "📱 MTN MoMo" },
  { value: "orange_money", label: "📱 Orange Money" },
  { value: "other", label: "⋯ Other" },
];

export default function PaymentPanel({
  method,
  onMethodChange,
  momoReference,
  onMomoReferenceChange,
  momoConfirmed,
  onMomoConfirmedChange,
}) {
  const isMomo = method === "mtn_momo" || method === "orange_money";

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
    </div>
  );
}
