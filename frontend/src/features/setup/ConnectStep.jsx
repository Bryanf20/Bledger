import { useState } from "react";
import { connectToHQ } from "../../api/sync";
import { extractErrorMessage } from "../../api/errors";

// Setup-wizard "Connect to head office" step (Phase 2 design §2.3). Redeems a
// one-time enrolment code minted by HQ; on success the device has a cloud
// identity and its users/catalogue are pulled, so the manager can sign in.
export default function ConnectStep({ onBack, onConnected }) {
  const [code, setCode] = useState("");
  const [cloudUrl, setCloudUrl] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const result = await connectToHQ({
        code: code.trim(),
        cloud_url: cloudUrl.trim() || undefined,
      });
      onConnected(result);
    } catch (err) {
      setError(extractErrorMessage(err, "Couldn’t connect. Check the code and try again."));
      setIsSubmitting(false);
    }
  }

  return (
    <form className="wiz-form" onSubmit={handleSubmit}>
      <div className="wiz-step-title">Connect to head office</div>
      <div className="wiz-step-sub">
        Enter the one-time enrolment code from your head office. This device
        joins as a branch and receives its products and staff automatically.
      </div>

      {error && (
        <div className="wiz-error-banner" role="alert">
          {error}
        </div>
      )}

      <div>
        <label className="wiz-field-label" htmlFor="enrol_code">
          Enrolment code
        </label>
        <input
          id="enrol_code"
          className="wiz-field-input"
          value={code}
          onChange={(e) => setCode(e.target.value.toUpperCase())}
          placeholder="e.g. ABCD2345"
          autoFocus
          disabled={isSubmitting}
        />
      </div>

      <div>
        <label className="wiz-field-label" htmlFor="cloud_url">
          Head office address{" "}
          <span className="wiz-field-hint">(optional — leave blank if preconfigured)</span>
        </label>
        <input
          id="cloud_url"
          className="wiz-field-input"
          value={cloudUrl}
          onChange={(e) => setCloudUrl(e.target.value)}
          placeholder="https://your-hq.example.com"
          disabled={isSubmitting}
        />
      </div>

      <div className="wiz-nav">
        <button type="button" className="wiz-btn" onClick={onBack} disabled={isSubmitting}>
          Back
        </button>
        <button type="submit" className="wiz-btn primary" disabled={isSubmitting || !code.trim()}>
          {isSubmitting ? "Connecting…" : "Connect"}
        </button>
      </div>
    </form>
  );
}
