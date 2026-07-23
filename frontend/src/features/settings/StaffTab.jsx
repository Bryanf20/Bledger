import { useState } from "react";
import Banner from "../../components/Banner";
import { extractErrorMessage } from "../../api/errors";
import { useAuth } from "../../context/AuthContext";
import {
  useCreateStaff,
  useResetStaffPin,
  useStaff,
  useUpdateStaff,
} from "../../hooks/useSettings";

// Staff management (§7.1). Owner adds/edits staff, deactivates (never
// deletes — sale/adjustment history references them), and resets PINs.
// A cashier authenticates by 4-digit PIN; a manager by password — so the
// create form asks for the right credential based on the chosen role.
export default function StaffTab({ onSuccess, onError }) {
  const { user } = useAuth();
  const { data: staff, isLoading, isError } = useStaff();
  const createStaff = useCreateStaff();
  const updateStaff = useUpdateStaff();
  const resetPin = useResetStaffPin();

  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ name: "", username: "", role: "cashier", pin: "", password: "" });
  const [resetFor, setResetFor] = useState(null);
  const [newPin, setNewPin] = useState("");

  if (isError) return <Banner type="error">Couldn&apos;t load staff.</Banner>;

  async function submitNew(e) {
    e.preventDefault();
    const payload = { name: form.name.trim(), username: form.username.trim(), role: form.role };
    if (form.role === "cashier") payload.pin = form.pin;
    else payload.password = form.password;
    try {
      await createStaff.mutateAsync(payload);
      setAdding(false);
      setForm({ name: "", username: "", role: "cashier", pin: "", password: "" });
      onSuccess(`${payload.name} added.`);
    } catch (err) {
      onError(extractErrorMessage(err, "Couldn't add that staff member."));
    }
  }

  async function toggleActive(member) {
    try {
      await updateStaff.mutateAsync({ id: member.id, payload: { is_active: !member.is_active } });
      onSuccess(member.is_active ? `${member.name} deactivated.` : `${member.name} reactivated.`);
    } catch (err) {
      onError(extractErrorMessage(err, "Couldn't update that account."));
    }
  }

  async function submitReset(member) {
    if (!/^\d{4}$/.test(newPin)) {
      onError("PIN must be 4 digits.");
      return;
    }
    try {
      await resetPin.mutateAsync({ id: member.id, pin: newPin });
      setResetFor(null);
      setNewPin("");
      onSuccess(`PIN reset for ${member.name}.`);
    } catch (err) {
      onError(extractErrorMessage(err, "Couldn't reset that PIN."));
    }
  }

  return (
    <div className="set-staff">
      <div className="set-staff-header">
        <span className="set-section-title">Staff accounts</span>
        {!adding && (
          <button type="button" className="set-submit set-inline" onClick={() => setAdding(true)}>
            + Add staff
          </button>
        )}
      </div>

      {adding && (
        <form className="set-form set-add-form" onSubmit={submitNew}>
          <label className="set-field">
            <span>Name *</span>
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} autoFocus />
          </label>
          <label className="set-field">
            <span>Username *</span>
            <input value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
          </label>
          <label className="set-field">
            <span>Role</span>
            <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
              <option value="cashier">Cashier (PIN login)</option>
              <option value="manager">Manager (password login)</option>
            </select>
          </label>
          {form.role === "cashier" ? (
            <label className="set-field">
              <span>4-digit PIN *</span>
              <input
                inputMode="numeric"
                maxLength={4}
                value={form.pin}
                onChange={(e) => setForm({ ...form, pin: e.target.value.replace(/\D/g, "") })}
              />
            </label>
          ) : (
            <label className="set-field">
              <span>Password *</span>
              <input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
            </label>
          )}
          <div className="set-add-actions">
            <button type="button" className="set-btn" onClick={() => setAdding(false)}>Cancel</button>
            <button type="submit" className="set-submit set-inline" disabled={createStaff.isPending}>
              {createStaff.isPending ? "Adding…" : "Add"}
            </button>
          </div>
        </form>
      )}

      {isLoading ? (
        <div className="set-empty">Loading…</div>
      ) : (
        <table className="set-table">
          <thead>
            <tr><th>Name</th><th>Username</th><th>Role</th><th>Status</th><th /></tr>
          </thead>
          <tbody>
            {(staff ?? []).map((m) => {
              const isSelf = m.id === user?.id;
              return (
                <tr key={m.id} className={m.is_active ? "" : "set-row-inactive"}>
                  <td>{m.name}{isSelf ? " (you)" : ""}</td>
                  <td>{m.username}</td>
                  <td className="set-role">{m.role}</td>
                  <td>{m.is_active ? "Active" : "Inactive"}</td>
                  <td className="set-row-actions">
                    {resetFor === m.id ? (
                      <span className="set-reset">
                        <input
                          inputMode="numeric"
                          maxLength={4}
                          placeholder="New PIN"
                          value={newPin}
                          onChange={(e) => setNewPin(e.target.value.replace(/\D/g, ""))}
                          autoFocus
                        />
                        <button type="button" className="set-btn" disabled={resetPin.isPending} onClick={() => submitReset(m)}>Save</button>
                        <button type="button" className="set-btn" onClick={() => { setResetFor(null); setNewPin(""); }}>Cancel</button>
                      </span>
                    ) : (
                      <>
                        {m.role === "cashier" && (
                          <button type="button" className="set-btn" onClick={() => { setResetFor(m.id); setNewPin(""); }}>Reset PIN</button>
                        )}
                        {!isSelf && (
                          <button type="button" className={`set-btn${m.is_active ? " danger" : ""}`} onClick={() => toggleActive(m)}>
                            {m.is_active ? "Deactivate" : "Reactivate"}
                          </button>
                        )}
                      </>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
