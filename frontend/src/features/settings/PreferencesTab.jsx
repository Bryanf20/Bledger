import { useEffect, useState } from "react";
import Banner from "../../components/Banner";
import { extractErrorMessage } from "../../api/errors";
import { usePreferences, useUpdatePreferences } from "../../hooks/useSettings";

// Business-wide policy defaults (§7.2). Percentages are whole numbers;
// default_credit_limit is XAF. These feed negotiated pricing, credit, and
// margin alerts — the consuming features enforce them, this just sets them.
const NUM_FIELDS = [
  { key: "default_discount_floor_pct", label: "Discount floor", suffix: "%", hint: "Deepest discount a cashier may give without approval." },
  { key: "default_surplus_ceiling_pct", label: "Surplus ceiling", suffix: "%", hint: "How far above catalogue price is allowed before approval." },
  { key: "price_deviation_alert_pct", label: "Price-deviation alert", suffix: "%", hint: "Flag sales that stray this far from catalogue price." },
  { key: "default_credit_limit", label: "Default credit limit", suffix: "XAF", hint: "Starting limit for a new credit customer." },
  { key: "margin_alert_pct", label: "Low-margin alert", suffix: "%", hint: "Flag products selling below this gross margin." },
];

export default function PreferencesTab({ onSuccess, onError }) {
  const { data, isLoading, isError } = usePreferences();
  const updatePreferences = useUpdatePreferences();
  const [form, setForm] = useState(null);

  useEffect(() => {
    if (data) {
      const next = {};
      NUM_FIELDS.forEach((f) => { next[f.key] = String(data[f.key] ?? 0); });
      setForm(next);
    }
  }, [data]);

  if (isError) return <Banner type="error">Couldn&apos;t load preferences.</Banner>;
  if (isLoading || !form) return <div className="set-empty">Loading…</div>;

  async function save(e) {
    e.preventDefault();
    const payload = {};
    NUM_FIELDS.forEach((f) => { payload[f.key] = Number(form[f.key]) || 0; });
    try {
      await updatePreferences.mutateAsync(payload);
      onSuccess("Preferences saved.");
    } catch (err) {
      onError(extractErrorMessage(err, "Couldn't save preferences."));
    }
  }

  return (
    <form className="set-form" onSubmit={save}>
      {NUM_FIELDS.map((f) => (
        <label className="set-field" key={f.key}>
          <span>{f.label}</span>
          <div className="set-suffixed">
            <input
              type="number"
              min="0"
              value={form[f.key]}
              onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
            />
            <span className="set-suffix">{f.suffix}</span>
          </div>
          <small className="set-hint">{f.hint}</small>
        </label>
      ))}

      <button type="submit" className="set-submit" disabled={updatePreferences.isPending}>
        {updatePreferences.isPending ? "Saving…" : "Save preferences"}
      </button>
    </form>
  );
}
