import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { loadTemplate } from "../../api/setup";
import { extractErrorMessage } from "../../api/errors";
import BusinessStep from "./BusinessStep";
import TemplateStep from "./TemplateStep";
import AccountStep from "./AccountStep";
import ConnectStep from "./ConnectStep";
import ThemeToggle from "../../components/ThemeToggle";
import "./SetupWizard.css";

const STEPS = [
  { number: 1, label: "Business" },
  { number: 2, label: "Products" },
  { number: 3, label: "Account" },
];

export default function SetupWizard() {
  const { completeSetup } = useAuth();
  const navigate = useNavigate();

  // null = choose a path; "new" = create a standalone business; "connect" =
  // enrol this device as a branch of an existing business (Phase 2 §2.3).
  const [mode, setMode] = useState(null);

  const [step, setStep] = useState(1);
  const [business, setBusiness] = useState(null);
  const [templateKey, setTemplateKey] = useState(undefined);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  function handleBusinessContinue(values) {
    setBusiness(values);
    setStep(2);
  }

  function handleTemplateContinue(key) {
    setTemplateKey(key);
    setStep(3);
  }

  async function handleFinish(accountValues) {
    setSubmitError(null);
    setIsSubmitting(true);
    try {
      const payload = {
        ...business,
        ...accountValues,
        pin: accountValues.pin || undefined,
      };
      await completeSetup(payload);

      if (templateKey) {
        try {
          await loadTemplate(templateKey);
        } catch {
          // Swallow -- owner can load a template later, or add products
          // manually from Inventory. Not worth blocking on.
        }
      }

      navigate("/", { replace: true });
    } catch (err) {
      setSubmitError(extractErrorMessage(err, "Couldn't complete setup. Please try again."));
      setIsSubmitting(false);
    }
  }

  function handleConnected() {
    // This device is now a branch: identity persisted, users + catalogue
    // pulled. Send the manager to sign in with their (synced) account.
    navigate("/login", { replace: true });
  }

  const subtitle = mode === "connect" ? "Connect to head office" : "First-time setup";

  return (
    <div className="wizard-page">
      <div className="wizard-shell">
        <div className="wiz-screen">
          <div className="wiz-header">
            <div className="wiz-header-top">
              <div>
                <span className="wiz-brand-name">Bledger</span>
                <span className="wiz-brand-sub">{subtitle}</span>
              </div>
              <ThemeToggle variant="on-brand" />
            </div>
            {mode === "new" && (
              <div className="wiz-steps-row">
                {STEPS.map((s) => (
                  <div
                    key={s.number}
                    className={`wiz-step${s.number === step ? " active" : ""}${s.number < step ? " done" : ""}`}
                  >
                    <div className="wiz-step-num">{s.number < step ? "✓" : s.number}</div>
                    <div className="wiz-step-label">{s.label}</div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="wiz-body">
            {mode === null && (
              <>
                <div className="wiz-step-title">Set up this device</div>
                <div className="wiz-step-sub">
                  Is this a brand-new business, or a branch of one you already run?
                </div>
                <div className="wiz-mode-choice">
                  <button type="button" className="wiz-mode-card" onClick={() => setMode("new")}>
                    <span className="wiz-mode-icon">🏪</span>
                    <span className="wiz-mode-name">Set up a new business</span>
                    <span className="wiz-mode-desc">A standalone shop that runs on this device.</span>
                  </button>
                  <button type="button" className="wiz-mode-card" onClick={() => setMode("connect")}>
                    <span className="wiz-mode-icon">🏢</span>
                    <span className="wiz-mode-name">Connect to head office</span>
                    <span className="wiz-mode-desc">
                      Join an existing business as a branch, using an enrolment code.
                    </span>
                  </button>
                </div>
              </>
            )}

            {mode === "connect" && (
              <ConnectStep onBack={() => setMode(null)} onConnected={handleConnected} />
            )}

            {mode === "new" && step === 1 && (
              <>
                <div className="wiz-step-title">Tell us about your business</div>
                <div className="wiz-step-sub">This appears on receipts and reports.</div>
                <BusinessStep defaultValues={business ?? {}} onContinue={handleBusinessContinue} />
              </>
            )}

            {mode === "new" && step === 2 && (
              <TemplateStep
                defaultTemplateKey={templateKey}
                onBack={() => setStep(1)}
                onContinue={handleTemplateContinue}
              />
            )}

            {mode === "new" && step === 3 && (
              <AccountStep
                defaultValues={{}}
                onBack={() => setStep(2)}
                onFinish={handleFinish}
                isSubmitting={isSubmitting}
                submitError={submitError}
              />
            )}
          </div>
        </div>

        <p className="wiz-caption">
          Bledger — First-run setup. Choose a new business or connect this device to head
          office as a branch.
        </p>
      </div>
    </div>
  );
}
