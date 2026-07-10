import "./DashboardBadges.css";

// Mirrors features/sales/SaleBadges.jsx and features/suppliers/
// SupplierBadges.jsx's approach: a per-feature badge file with its
// own dash- prefixed classes, rather than a shared components/
// promotion -- same "duplicate per screen, promote later if a THIRD
// screen needs it" convention already used twice in this project.
//
// PAYMENT_VARIANTS mirrors SaleBadges.jsx's mapping exactly (same
// [DEVIATION -- FLAGGED] reasoning: the doc only specifies "MoMo
// panel = warning", mtn_momo keeps that, orange_money uses info to
// stay visually distinct from MTN, cash/other are neutral) -- kept in
// sync here rather than imported cross-feature, consistent with how
// SupplierBadges.css independently restates SaleBadges.css's pill
// base rather than importing it.
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
  return <span className={`dash-badge dash-badge-${variant}`}>{PAYMENT_LABELS[method] ?? method}</span>;
}

// Stock alert severity dot -- "low" (warning/amber) vs "out"
// (danger/red), matching StockAlertSerializer's `status` field and
// the same success/warning/danger semantic mapping Inventory's stock
// badges already use.
export function StockSeverityDot({ status }) {
  return <span className={`dash-severity-dot dash-severity-${status === "out" ? "danger" : "warning"}`} />;
}
