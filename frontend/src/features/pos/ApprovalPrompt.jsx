import { useState } from "react";
import { verifyPin } from "../../api/auth";

// Manager PIN-approval prompt (Phase 2 §3.2). Shown when a sale contains
// a price outside the allowed band: a manager enters their username +
// PIN, and on success we get a short-lived approval token that the sale
// POST carries. Confined to the POS right panel like the other overlays.
//
// This does NOT log the manager in — verify-pin is an authorisation
// check inside the cashier's session (the backend guarantees this).
export default function ApprovalPrompt({ purpose, title, subtitle, onCancel, onApproved }) {
  const [username, setUsername] = useState("");
  const [pin, setPin] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const canSubmit = username.trim() && pin.length === 4 && !busy;

  async function submit() {
    setError(null);
    setBusy(true);
    try {
      const { approval_token } = await verifyPin({
        username: username.trim(),
        pin,
        purpose,
      });
      onApproved(approval_token);
    } catch (err) {
      const status = err.response?.status;
      setError(
        status === 429
          ? "Too many attempts. Try again in a few minutes."
          : "That username or PIN wasn't accepted, or that person can't approve.",
      );
      setPin("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="inline-confirm-backdrop">
      <div className="inline-confirm">
        <p className="inline-confirm-title">{title ?? "Manager approval needed"}</p>
        {subtitle && <p className="inline-confirm-sub">{subtitle}</p>}

        <label className="pos-brokered-label" htmlFor="appr-user">Manager username</label>
        <input
          id="appr-user"
          type="text"
          className="inline-confirm-input"
          autoComplete="off"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoFocus
        />

        <label className="pos-brokered-label" htmlFor="appr-pin">Manager PIN</label>
        <input
          id="appr-pin"
          type="password"
          inputMode="numeric"
          maxLength={4}
          className="inline-confirm-input"
          value={pin}
          onChange={(e) => setPin(e.target.value.replace(/\D/g, "").slice(0, 4))}
        />

        {error && <p className="pos-brokered-gain loss">{error}</p>}

        <div className="inline-confirm-actions">
          <button type="button" className="inline-confirm-cancel-btn" onClick={onCancel}>
            Cancel
          </button>
          <button
            type="button"
            className="inline-confirm-btn"
            disabled={!canSubmit}
            onClick={submit}
          >
            {busy ? "Checking…" : "Approve"}
          </button>
        </div>
      </div>
    </div>
  );
}
