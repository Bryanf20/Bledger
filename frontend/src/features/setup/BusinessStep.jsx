import { useForm } from "react-hook-form";

// Maps directly onto SetupSerializer's step-1 fields (see
// apps/auth_users/serializers.py in project knowledge): business_name
// and phone are required there; branch_name, address, receipt_footer
// are all `required=False, allow_blank=True`.
export default function BusinessStep({ defaultValues, onContinue }) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm({ defaultValues });

  return (
    <form className="wiz-form" onSubmit={handleSubmit(onContinue)}>
      <div>
        <label className="wiz-field-label" htmlFor="business_name">
          Business name
        </label>
        <input
          id="business_name"
          className="wiz-field-input"
          placeholder="e.g. Ambe & Sons Provisions"
          {...register("business_name", { required: "Business name is required." })}
        />
        {errors.business_name && <div className="wiz-field-error">{errors.business_name.message}</div>}
      </div>

      <div>
        <label className="wiz-field-label" htmlFor="branch_name">
          Branch name <span className="wiz-field-hint">(optional)</span>
        </label>
        <input
          id="branch_name"
          className="wiz-field-input"
          placeholder="e.g. Main Branch"
          {...register("branch_name")}
        />
      </div>

      <div>
        <label className="wiz-field-label" htmlFor="phone">
          Phone number
        </label>
        <input
          id="phone"
          className="wiz-field-input"
          placeholder="e.g. 6XX XXX XXX"
          {...register("phone", { required: "Phone number is required." })}
        />
        {errors.phone && <div className="wiz-field-error">{errors.phone.message}</div>}
      </div>

      <div>
        <label className="wiz-field-label" htmlFor="address">
          Address <span className="wiz-field-hint">(optional)</span>
        </label>
        <input id="address" className="wiz-field-input" placeholder="e.g. Molyko, Buea" {...register("address")} />
      </div>

      <div>
        <label className="wiz-field-label" htmlFor="receipt_footer">
          Receipt footer <span className="wiz-field-hint">(optional)</span>
        </label>
        <input
          id="receipt_footer"
          className="wiz-field-input"
          placeholder="e.g. Thank you for your business!"
          {...register("receipt_footer")}
        />
      </div>

      <div className="wiz-nav">
        <button type="submit" className="wiz-btn primary">
          Continue
        </button>
      </div>
    </form>
  );
}
