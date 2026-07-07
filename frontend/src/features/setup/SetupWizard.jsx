import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { loadTemplate } from "../../api/setup";
import { extractErrorMessage } from "../../api/errors";
import BusinessStep from "./BusinessStep";
import TemplateStep from "./TemplateStep";
import AccountStep from "./AccountStep";
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
          // Swallow -- owner can load a template later, or add
          // products manually from Inventory. Not worth blocking on.
        }
      }

      navigate("/", { replace: true });
    } catch (err) {
      setSubmitError(extractErrorMessage(err, "Couldn't complete setup. Please try again."));
      setIsSubmitting(false);
    }
  }

  return (
    <div className="wizard-page">
      <div className="wizard-shell">
        <div className="screen">
          <div className="wiz-header">
            <div className="wiz-header-top">
              <div>
                <span className="wiz-brand-name">Bledger</span>
                <span className="wiz-brand-sub">First-time setup</span>
              </div>
              <ThemeToggle variant="on-brand" />
            </div>
            <div className="steps-row">
              {STEPS.map((s) => (
                <div
                  key={s.number}
                  className={`step${s.number === step ? " active" : ""}${s.number < step ? " done" : ""}`}
                >
                  <div className="step-num">{s.number < step ? "✓" : s.number}</div>
                  <div className="step-label">{s.label}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="wiz-body">
            {step === 1 && (
              <>
                <div className="step-title">Tell us about your business</div>
                <div className="step-sub">This appears on receipts and reports.</div>
                <BusinessStep defaultValues={business ?? {}} onContinue={handleBusinessContinue} />
              </>
            )}

            {step === 2 && (
              <TemplateStep
                defaultTemplateKey={templateKey}
                onBack={() => setStep(1)}
                onContinue={handleTemplateContinue}
              />
            )}

            {step === 3 && (
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

        <p className="caption">
          Bledger — First-run Setup Wizard, Step {step} of 3. Business details → Product
          template selection → Owner account creation.
        </p>
      </div>
    </div>
  );
}
