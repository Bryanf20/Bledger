import "./InlineConfirm.css";

// Shared "confined to panel" confirmation overlay -- replaces
// window.prompt()/window.confirm() so blocking/destructive actions
// (POS hold-sale, POS clear-cart, Receipt void-sale) match the app's
// own theme instead of an unstyled OS dialog.
//
// Absolutely positioned at inset:0 with z-index:10 -- the parent panel
// (POS's .pos-right-panel, Receipt's .receipt-right) must itself set
// position: relative so this is clipped to that panel, not the
// viewport. This component doesn't set that positioning itself, since
// it doesn't own the panel.
//
// `input` (optional): pass { value, onChange, placeholder } when the
// action needs free text (hold label, void reason). Omit it entirely
// for a plain yes/no confirmation (clear cart).
export default function InlineConfirm({
  title,
  subtitle,
  input,
  onCancel,
  cancelLabel = "Cancel",
  onConfirm,
  confirmLabel,
  confirmPendingLabel,
  isPending = false,
  confirmDisabled = false,
  danger = false,
}) {
  return (
    <div className="inline-confirm-backdrop">
      <div className="inline-confirm">
        <p className="inline-confirm-title">{title}</p>
        {subtitle && <p className="inline-confirm-sub">{subtitle}</p>}
        {input && (
          <input
            type="text"
            className="inline-confirm-input"
            placeholder={input.placeholder}
            value={input.value}
            onChange={input.onChange}
            autoFocus
          />
        )}
        <div className="inline-confirm-actions">
          <button type="button" className="inline-confirm-cancel-btn" onClick={onCancel}>
            {cancelLabel}
          </button>
          <button
            type="button"
            className={`inline-confirm-btn${danger ? " inline-confirm-btn-danger" : ""}`}
            onClick={onConfirm}
            disabled={confirmDisabled || isPending}
          >
            {isPending ? (confirmPendingLabel ?? confirmLabel) : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
