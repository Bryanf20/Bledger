import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { hasRole } from "../../components/RoleGuard";
import Banner from "../../components/Banner";
import InlineConfirm from "../../components/InlineConfirm";
import ScreenTopbar from "../../components/ScreenTopbar";
import ToastStack from "../../components/ToastStack";
import XAFAmount from "../../components/XAFAmount";
import { useSale, useVoidSale } from "../../hooks/useSale";
import { fetchReceiptPdf } from "../../api/sales";
import { downloadBlob } from "../../utils/downloadBlob";
import { useToasts } from "../../hooks/useToasts";
import "./ReceiptScreen.css";

const PAYMENT_LABELS = {
  cash: "Cash",
  mtn_momo: "MTN MoMo",
  orange_money: "Orange Money",
  other: "Other",
};

function formatDate(iso) {
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  return `${dd}/${mm}/${d.getFullYear()}`;
}

function formatTime(iso) {
  const d = new Date(iso);
  return d.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export default function ReceiptScreen() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user, role } = useAuth();
  const { data: sale, isLoading, isError } = useSale(id);
  const voidSaleMutation = useVoidSale(id);

  const [showVoidConfirm, setShowVoidConfirm] = useState(false);
  const [voidReason, setVoidReason] = useState("");
  const [isDownloading, setIsDownloading] = useState(false);
  // PDF-download failures now go through toasts (transient action
  // feedback) instead of the old local .receipt-error-banner div --
  // that div was never actually routed through the shared <Banner>
  // component to begin with (a leftover from before Banner.jsx
  // unified things). The isError/!sale early-return below is a
  // genuine persistent/blocking state and is untouched by this change.
  const { toasts, showToast, dismissToast } = useToasts();

  const canVoid = hasRole(role, "manager");

  async function handleDownloadPdf() {
    setIsDownloading(true);
    try {
      const blob = await fetchReceiptPdf(id);
      downloadBlob(blob, `receipt-${sale.reference}.pdf`);
    } catch (err) {
      showToast(
        "error",
        err.response?.status === 503
          ? "PDF receipts aren't available on this install yet (missing printer setup)."
          : "Couldn't download the receipt. Please try again.",
      );
    } finally {
      setIsDownloading(false);
    }
  }

  async function handleConfirmVoid() {
    if (!voidReason.trim()) return;
    await voidSaleMutation.mutateAsync(voidReason.trim());
    setShowVoidConfirm(false);
    setVoidReason("");
  }

  if (isLoading) {
    return (
      <div className="receipt-page">
        <div className="receipt-shell">
          <div className="receipt-screen">
            <div className="receipt-empty-state">Loading receipt…</div>
          </div>
        </div>
      </div>
    );
  }

  if (isError || !sale) {
    return (
      <div className="receipt-page">
        <div className="receipt-shell">
          <div className="receipt-screen">
            <div className="receipt-empty-state">Couldn&apos;t find that sale.</div>
            <button type="button" className="receipt-action-btn primary" onClick={() => navigate("/pos")}>
              Back to POS
            </button>
          </div>
        </div>
      </div>
    );
  }

  const isVoided = sale.status === "voided";
  const isMomo = sale.payment_method === "mtn_momo" || sale.payment_method === "orange_money";
  const paymentLabel = PAYMENT_LABELS[sale.payment_method] ?? sale.payment_method;
  const unitsCount = sale.line_items.reduce((sum, item) => sum + item.quantity, 0);
  const saleNumber = sale.reference.split("-").pop();

  return (
    <div className="receipt-page">
      {/* .receipt-shell is the one place that owns the column layout
          and the height:100%/min-height:0 chain (see ReceiptScreen.css
          header comment) -- .receipt-page just centers it. Height,
          not min-height, all the way down, so a long line-item list
          scrolls inside .receipt-left instead of growing the page and
          silently breaking that overflow-y. */}
      <div className="receipt-shell">
        <div className="receipt-screen">
          <ScreenTopbar
            title={`Bledger — ${isVoided ? "Sale voided" : "Sale complete"}`}
            meta={
              <span>
                👤 {user?.name} · {user?.branch?.branch_name}
              </span>
            }
          />

          <div className="receipt-body">
            <div className="receipt-left">
              {isVoided ? (
                <div className="receipt-status-bar voided">
                  <div className="receipt-status-icon">↩</div>
                  <div>
                    <div className="receipt-status-title">This sale was voided</div>
                    <div className="receipt-status-sub">
                      {sale.void_reason}
                      {sale.voided_at ? ` · ${formatDate(sale.voided_at)} ${formatTime(sale.voided_at)}` : ""}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="receipt-status-bar success">
                  <div className="receipt-status-icon">✓</div>
                  <div>
                    <div className="receipt-status-title">Sale confirmed</div>
                    <div className="receipt-status-sub">
                      <XAFAmount value={sale.total_amount} /> · {paymentLabel}
                      {isMomo && sale.momo_reference ? ` · Ref: ${sale.momo_reference}` : ""}
                    </div>
                  </div>
                </div>
              )}

              {/* Receipt paper stays fixed light/white regardless of
                  app theme, same convention as the brand-navy login
                  panel: it represents a physical printed receipt, not
                  a themed app surface, so it doesn't invert in dark
                  mode. */}
              <div className="receipt-paper-wrap">
                <div className="receipt-paper">
                  <p className="receipt-r-biz receipt-r-center">{user?.branch?.business_name}</p>
                  <p className="receipt-r-center receipt-r-muted">
                    {user?.branch?.address} · Tel: {user?.branch?.phone}
                  </p>
                  <hr className="receipt-r-divider" />
                  <div className="receipt-r-item">
                    <span>Date: {formatDate(sale.created_at)}</span>
                    <span>{formatTime(sale.created_at)}</span>
                  </div>
                  <div className="receipt-r-item">
                    <span>Cashier: {sale.cashier_name}</span>
                    <span>Sale #{saleNumber}</span>
                  </div>
                  <hr className="receipt-r-divider" />
                  {sale.line_items.map((item) => (
                    <div className="receipt-r-item" key={item.id}>
                      <span>
                        {item.product_name} ×{item.quantity}
                      </span>
                      <span>
                        <XAFAmount value={item.line_total} />
                      </span>
                    </div>
                  ))}
                  <hr className="receipt-r-divider" />
                  <div className="receipt-r-total">
                    <span>Subtotal</span>
                    <XAFAmount value={sale.subtotal} />
                  </div>
                  <div className="receipt-r-total">
                    <span>Tax</span>
                    <XAFAmount value={sale.tax_amount} />
                  </div>
                  <div className="receipt-r-total receipt-r-grand">
                    <span>Total</span>
                    <XAFAmount value={sale.total_amount} />
                  </div>
                  <hr className="receipt-r-divider" />
                  <p className="receipt-r-center">Paid by {paymentLabel}</p>
                  {isMomo && sale.momo_reference && (
                    <p className="receipt-r-center receipt-r-muted">Ref: {sale.momo_reference}</p>
                  )}
                  <hr className="receipt-r-divider" />
                  <p className="receipt-r-center receipt-r-muted">
                    {user?.branch?.receipt_footer || "Thank you for shopping with us!"}
                  </p>
                  <p className="receipt-r-center receipt-r-muted">REF: {sale.reference}</p>
                </div>
              </div>
            </div>

            <div className="receipt-right">
              <div className="receipt-right-scroll">
                <div className="receipt-summary-card">
                  <div className="receipt-summary-row">
                    <span>Total</span>
                    <b>
                      <XAFAmount value={sale.total_amount} />
                    </b>
                  </div>
                  <div className="receipt-summary-row">
                    <span>Items</span>
                    <span>
                      {sale.line_items.length} products · {unitsCount} units
                    </span>
                  </div>
                  <div className="receipt-summary-row">
                    <span>Payment</span>
                    <span>{paymentLabel}</span>
                  </div>
                  <div className="receipt-summary-row">
                    <span>Cashier</span>
                    <span>{sale.cashier_name}</span>
                  </div>
                  <div className="receipt-summary-row">
                    <span>Sale ref</span>
                    <span>{sale.reference}</span>
                  </div>
                </div>

                <button
                  type="button"
                  className="receipt-action-btn"
                  onClick={handleDownloadPdf}
                  disabled={isDownloading}
                >
                  ⬇ {isDownloading ? "Preparing…" : "Download PDF receipt"}
                </button>
                <button type="button" className="receipt-action-btn" disabled title="Phase 3">
                  🖨 Print receipt <span className="receipt-badge">Phase 3</span>
                </button>
                <button type="button" className="receipt-action-btn" disabled title="Coming later">
                  ↗ Share receipt <span className="receipt-badge">future</span>
                </button>
              </div>

              <div className="receipt-right-footer">
                {canVoid && !isVoided && (
                  <button type="button" className="receipt-action-btn" onClick={() => setShowVoidConfirm(true)}>
                    ↩ Void this sale
                  </button>
                )}
                <button type="button" className="receipt-action-btn primary" onClick={() => navigate("/pos")}>
                  + New sale
                </button>
              </div>
              {showVoidConfirm && (
                <InlineConfirm
                  title="Void this sale"
                  subtitle="This restores stock for every line item and can't be undone."
                  input={{
                    value: voidReason,
                    onChange: (e) => setVoidReason(e.target.value),
                    placeholder: "Reason (required)",
                  }}
                  onCancel={() => {
                    setShowVoidConfirm(false);
                    setVoidReason("");
                  }}
                  onConfirm={handleConfirmVoid}
                  confirmLabel="Void sale"
                  confirmPendingLabel="Voiding…"
                  isPending={voidSaleMutation.isPending}
                  confirmDisabled={!voidReason.trim()}
                  danger
                />
              )}
            </div>
          </div>
        </div>

        <ToastStack toasts={toasts} onDismiss={dismissToast} />
      </div>
    </div>
  );
}
