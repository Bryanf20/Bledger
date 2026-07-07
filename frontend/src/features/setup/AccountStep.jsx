import { useForm } from "react-hook-form";

// Maps onto SetupSerializer's step-3 fields: owner_name, username,
// password (min_length=8), and an optional 4-digit pin for mobile
// quick access (design doc B.7 step 3 -- owner/manager may *optionally*
// also set a PIN; only cashiers are PIN-only).
export default function AccountStep({ defaultValues, onBack, onFinish, isSubmitting, submitError }) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm({ defaultValues });

  return (
    <form className="wiz-form" onSubmit={handleSubmit(onFinish)}>
      <div className="step-title">Create your owner account</div>
      <div className="step-sub">This is the account you&apos;ll use to sign in and manage the business.</div>

      {submitError && (
        <div className="error-banner" role="alert">
          {submitError}
        </div>
      )}

      <div>
        <label className="field-label" htmlFor="owner_name">
          Your name
        </label>
        <input
          id="owner_name"
          className="field-input"
          disabled={isSubmitting}
          {...register("owner_name", { required: "Your name is required." })}
        />
        {errors.owner_name && <div className="field-error">{errors.owner_name.message}</div>}
      </div>

      <div>
        <label className="field-label" htmlFor="username">
          Username
        </label>
        <input
          id="username"
          className="field-input"
          autoComplete="username"
          disabled={isSubmitting}
          {...register("username", { required: "Username is required." })}
        />
        {errors.username && <div className="field-error">{errors.username.message}</div>}
      </div>

      <div>
        <label className="field-label" htmlFor="password">
          Password
        </label>
        <input
          id="password"
          type="password"
          className="field-input"
          autoComplete="new-password"
          disabled={isSubmitting}
          {...register("password", {
            required: "Password is required.",
            minLength: { value: 8, message: "Password must be at least 8 characters." },
          })}
        />
        {errors.password && <div className="field-error">{errors.password.message}</div>}
      </div>

      <div>
        <label className="field-label" htmlFor="pin">
          4-digit PIN <span className="field-hint">(optional -- for fast mobile sign-in)</span>
        </label>
        <input
          id="pin"
          className="field-input"
          inputMode="numeric"
          maxLength={4}
          disabled={isSubmitting}
          {...register("pin", {
            validate: (value) =>
              !value || /^\d{4}$/.test(value) || "PIN must be exactly 4 digits.",
          })}
        />
        {errors.pin && <div className="field-error">{errors.pin.message}</div>}
      </div>

      <div className="wiz-nav">
        <button type="button" className="wiz-btn" onClick={onBack} disabled={isSubmitting}>
          Back
        </button>
        <button type="submit" className="wiz-btn primary" disabled={isSubmitting}>
          {isSubmitting ? "Setting up…" : "Finish setup"}
        </button>
      </div>
    </form>
  );
}
