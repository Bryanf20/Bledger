import "./SupplierBadges.css";

// Mirrors features/sales/SaleBadges.jsx's approach: kept local to
// features/suppliers/ rather than promoted to components/ until a
// second screen needs it, same "promote later if reused" rule.
//
// The UI Design Reference's "Payment status badge" description only
// covers two states explicitly -- green "Paid" and amber "Partial ·
// [amount]" -- because the reviewed wireframe (04_suppliers.html)
// only has paid/partial rows in its sample data. Purchase.payment_status
// has a third real value, "credit" (see backend/apps/suppliers/models.py),
// for amount_paid <= 0. [DEVIATION -- FLAGGED] Credit isn't specified
// anywhere in the doc, so it's given its own treatment here rather
// than folded into "Partial": danger/red, since an entirely unpaid
// purchase reads as more urgent than a partially-paid one, matching
// the same success/warning/danger semantic mapping used everywhere
// else in the app (stock status, sale status).
const LABELS = {
  paid: "Paid",
  partial: "Partial",
  credit: "Credit",
};

const VARIANTS = {
  paid: "success",
  partial: "warning",
  credit: "danger",
};

const moneyFormatter = new Intl.NumberFormat("en-US");

// amountPaid/totalAmount are optional -- when passed, the doc's
// "Partial · [amount]" convention is followed ("showing exactly how
// much has been paid toward the total"). Omit them for the live
// preview badge in RecordPurchaseForm, which doesn't have a real
// amount_paid figure to attach until the purchase is actually saved.
export function PaymentStatusBadge({ status, amountPaid }) {
  const variant = VARIANTS[status] ?? "neutral";
  const label = LABELS[status] ?? status;
  const showAmount = status === "partial" && amountPaid != null;
  return (
    <span className={`sup-badge sup-badge-${variant}`}>
      {label}
      {showAmount ? ` · ${moneyFormatter.format(amountPaid)} XAF` : ""}
    </span>
  );
}
