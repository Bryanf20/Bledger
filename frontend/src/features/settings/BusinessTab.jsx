import { useEffect, useState } from "react";
import Banner from "../../components/Banner";
import { extractErrorMessage } from "../../api/errors";
import { useBusiness, useUpdateBusiness } from "../../hooks/useSettings";

// Editable Branch details (§7.2). `code` is immutable after setup — it's
// baked into every sale reference — so it's shown read-only, not edited.
const FIELDS = [
  { key: "business_name", label: "Business name", required: true },
  { key: "branch_name", label: "Branch name" },
  { key: "address", label: "Address" },
  { key: "phone", label: "Phone" },
  { key: "receipt_footer", label: "Receipt footer", textarea: true },
];

export default function BusinessTab({ onSuccess, onError }) {
  const { data, isLoading, isError } = useBusiness();
  const updateBusiness = useUpdateBusiness();
  const [form, setForm] = useState(null);

  useEffect(() => {
    if (data) {
      setForm({
        business_name: data.business_name ?? "",
        branch_name: data.branch_name ?? "",
        address: data.address ?? "",
        phone: data.phone ?? "",
        receipt_footer: data.receipt_footer ?? "",
      });
    }
  }, [data]);

  if (isError) return <Banner type="error">Couldn&apos;t load business details.</Banner>;
  if (isLoading || !form) return <div className="set-empty">Loading…</div>;

  async function save(e) {
    e.preventDefault();
    if (!form.business_name.trim()) return;
    try {
      await updateBusiness.mutateAsync(form);
      onSuccess("Business details saved.");
    } catch (err) {
      onError(extractErrorMessage(err, "Couldn't save business details."));
    }
  }

  return (
    <form className="set-form" onSubmit={save}>
      <div className="set-field">
        <span>Branch code</span>
        <input type="text" value={data.code || ""} disabled />
        <small className="set-hint">Fixed after setup — it&apos;s part of every sale reference.</small>
      </div>

      {FIELDS.map((f) => (
        <label className="set-field" key={f.key}>
          <span>{f.label}{f.required ? " *" : ""}</span>
          {f.textarea ? (
            <textarea
              rows={3}
              value={form[f.key]}
              onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
            />
          ) : (
            <input
              type="text"
              value={form[f.key]}
              onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
            />
          )}
        </label>
      ))}

      <button type="submit" className="set-submit" disabled={updateBusiness.isPending || !form.business_name.trim()}>
        {updateBusiness.isPending ? "Saving…" : "Save changes"}
      </button>
    </form>
  );
}
