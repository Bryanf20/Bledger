import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { extractErrorMessage } from "../../api/errors";
import PINKeypad from "./PINKeypad";
import "./LoginScreen.css";

const ROLES = [
  { key: "cashier", label: "Cashier", icon: "👤" },
  { key: "manager", label: "Manager", icon: "👥" },
  { key: "owner", label: "Owner", icon: "🛡" },
];

const PIN_LENGTH = 4;

export default function LoginScreen() {
  const { login, pinLogin, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  const [selectedRole, setSelectedRole] = useState("cashier");
  const [username, setUsername] = useState("");
  const [pin, setPin] = useState("");
  const [error, setError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm({ defaultValues: { password: "" } });

  useEffect(() => {
    if (isAuthenticated) navigate("/", { replace: true });
  }, [isAuthenticated, navigate]);

  // Auto-submit the PIN login the moment 4 digits are entered -- this
  // is the "fast access" cashier flow the design doc describes; making
  // the cashier press an extra Sign In button would defeat the point.
  useEffect(() => {
    if (selectedRole !== "cashier" || pin.length !== PIN_LENGTH) return;
    if (!username.trim()) {
      setError("Enter your username first.");
      setPin("");
      return;
    }

    let cancelled = false;
    setIsSubmitting(true);
    setError(null);

    pinLogin(username.trim(), pin)
      .then(() => {
        if (!cancelled) navigate("/", { replace: true });
      })
      .catch((err) => {
        if (cancelled) return;
        setError(extractErrorMessage(err, "Invalid username or PIN."));
        setPin("");
      })
      .finally(() => {
        if (!cancelled) setIsSubmitting(false);
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pin]);

  function handleRoleChange(roleKey) {
    setSelectedRole(roleKey);
    setError(null);
    setPin("");
  }

  async function onPasswordSubmit({ password }) {
    setError(null);
    setIsSubmitting(true);
    try {
      await login(username.trim(), password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(extractErrorMessage(err, "Invalid username or password."));
    } finally {
      setIsSubmitting(false);
    }
  }

  const isCashierFlow = selectedRole === "cashier";

  return (
    <div className="login-page">
      <div className="wrap">
        <div className="left-panel">
          <div>
            <div className="brand-name">Bledger</div>
            <div className="brand-sub">Business Ledger</div>
            <div className="brand-tagline">
              Built for Anglophone Cameroonian businesses. Works online, offline, and
              everywhere in between.
            </div>
          </div>
          <div>
            <div className="feature">• Runs fully offline — no internet needed</div>
            <div className="feature">• Sales, inventory &amp; supplier tracking</div>
            <div className="feature">• MTN MoMo &amp; Orange Money support</div>
            <div className="feature">• PDF receipts in XAF</div>
          </div>
        </div>

        <div className="right-panel">
          <div className="login-title">Welcome back</div>
          <div className="login-sub">Standalone mode</div>

          {error && (
            <div className="error-banner" role="alert">
              {error}
            </div>
          )}

          <div className="role-selector" role="tablist" aria-label="Login method">
            {ROLES.map((r) => (
              <button
                key={r.key}
                type="button"
                role="tab"
                aria-selected={selectedRole === r.key}
                className={`role-card${selectedRole === r.key ? " active" : ""}`}
                onClick={() => handleRoleChange(r.key)}
              >
                {r.icon}
                <br />
                {r.label}
              </button>
            ))}
          </div>

          <div className="username-field">
            <label className="field-label" htmlFor="username">
              Username
            </label>
            <input
              id="username"
              className="field-input"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              disabled={isSubmitting}
            />
          </div>

          {isCashierFlow ? (
            <PINKeypad value={pin} onChange={setPin} length={PIN_LENGTH} disabled={isSubmitting} />
          ) : (
            <form className="password-form" onSubmit={handleSubmit(onPasswordSubmit)}>
              <div>
                <label className="field-label" htmlFor="password">
                  Password
                </label>
                <input
                  id="password"
                  type="password"
                  className="field-input"
                  autoComplete="current-password"
                  disabled={isSubmitting}
                  {...register("password", { required: "Password is required." })}
                />
                {errors.password && (
                  <div className="error-banner" style={{ marginTop: 8 }}>
                    {errors.password.message}
                  </div>
                )}
              </div>
              <button type="submit" className="submit-button" disabled={isSubmitting}>
                {isSubmitting ? "Signing in…" : "Sign in"}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
