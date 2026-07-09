import "./ToastStack.css";

// Fixed-position, bottom-right stack of ephemeral action-feedback
// notifications (saved / added / deactivated / error) -- distinct
// from Banner, which is for persistent, blocking screen states like
// "couldn't load this screen's data" and should stay on screen until
// the underlying problem is fixed.
export default function ToastStack({ toasts, onDismiss }) {
  if (!toasts.length) return null;

  return (
    <div className="toast-stack" role="status" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={`toast toast-${t.type}`}>
          <span className="toast-message">{t.message}</span>
          <button type="button" className="toast-close" onClick={() => onDismiss(t.id)} aria-label="Dismiss">
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
