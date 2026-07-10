import "./SaleBadges.css";

// Shared pill-badge components for SalesHistoryScreen's table and
// card views. Kept local to features/sales/ rather than promoted to
// components/ -- if a future screen (e.g. Dashboard's payment
// breakdown widget) needs the same payment-method badge, promote
// this file then.
//
// The design tokens only define 4 semantic colors (success/warning/
// danger/info); the UI Design Reference doesn't assign a color per
// payment method beyond "MoMo panel = warning" (POS's PaymentPanel).
// [DEVIATION -- FLAGGED] mtn_momo keeps that established warning/
// amber; orange_money uses info/blue purely to stay visually
// distinct from MTN at a glance (both are Mobile Money and would
// otherwise look identical) -- not specified anywhere, picked here.
// cash/other use a plain neutral pill.
const PAYMENT_LABELS = {
  cash: "Cash",
  mtn_momo: "MTN MoMo",
  orange_money: "Orange Money",
  other: "Other",
};

const PAYMENT_VARIANTS = {
  cash: "neutral",
  mtn_momo: "warning",
  orange_money: "info",
  other: "neutral",
};

export function PaymentMethodBadge({ method }) {
  const variant = PAYMENT_VARIANTS[method] ?? "neutral";
  return <span className={`sale-badge sale-badge-${variant}`}>{PAYMENT_LABELS[method] ?? method}</span>;
}

export function SaleStatusBadge({ status }) {
  const isVoided = status === "voided";
  return (
    <span className={`sale-badge sale-badge-${isVoided ? "danger" : "success"}`}>
      {isVoided ? "Voided" : "Completed"}
    </span>
  );
}
