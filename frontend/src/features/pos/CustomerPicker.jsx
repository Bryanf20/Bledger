import { useMemo, useState } from "react";
import { useCustomers, useCreateCustomer } from "../../hooks/useCustomers";

// Choose (or quickly add) the customer for a credit sale (Phase 2 §4).
// A cashier can register a walk-in on the spot; that customer starts with
// a 0 credit limit (so the sale needs manager approval) until a manager
// raises it. Confined to the POS right panel like the other overlays.
export default function CustomerPicker({ onCancel, onPick }) {
  const { data: customers, isLoading } = useCustomers();
  const createCustomer = useCreateCustomer();

  const [search, setSearch] = useState("");
  const [adding, setAdding] = useState(false);
  const [newName, setNewName] = useState("");
  const [newPhone, setNewPhone] = useState("");
  const [error, setError] = useState(null);

  const visible = useMemo(() => {
    const list = customers ?? [];
    const q = search.trim().toLowerCase();
    if (!q) return list;
    return list.filter(
      (c) => c.name.toLowerCase().includes(q) || (c.phone || "").includes(q),
    );
  }, [customers, search]);

  async function handleAdd() {
    if (!newName.trim()) return;
    setError(null);
    try {
      const created = await createCustomer.mutateAsync({ name: newName.trim(), phone: newPhone.trim() });
      onPick(created);
    } catch {
      setError("Couldn't add that customer.");
    }
  }

  return (
    <div className="inline-confirm-backdrop">
      <div className="inline-confirm pos-customer-picker">
        <p className="inline-confirm-title">Choose customer</p>

        {!adding ? (
          <>
            <input
              type="text"
              className="inline-confirm-input"
              placeholder="Search name or phone…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              autoFocus
            />
            <div className="pos-customer-list">
              {isLoading ? (
                <div className="pos-empty-state">Loading…</div>
              ) : visible.length === 0 ? (
                <div className="pos-empty-state">No customers found.</div>
              ) : (
                visible.map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    className="pos-customer-row"
                    onClick={() => onPick(c)}
                  >
                    <span>{c.name}</span>
                    <span className="pos-customer-owes">
                      owes {new Intl.NumberFormat("en-US").format(c.balance)}
                    </span>
                  </button>
                ))
              )}
            </div>
            <div className="inline-confirm-actions">
              <button type="button" className="inline-confirm-cancel-btn" onClick={onCancel}>
                Cancel
              </button>
              <button type="button" className="inline-confirm-btn" onClick={() => setAdding(true)}>
                + New customer
              </button>
            </div>
          </>
        ) : (
          <>
            <input
              type="text"
              className="inline-confirm-input"
              placeholder="Customer name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              autoFocus
            />
            <input
              type="text"
              className="inline-confirm-input"
              placeholder="Phone (optional)"
              value={newPhone}
              onChange={(e) => setNewPhone(e.target.value)}
            />
            {error && <p className="pos-brokered-gain loss">{error}</p>}
            <div className="inline-confirm-actions">
              <button type="button" className="inline-confirm-cancel-btn" onClick={() => setAdding(false)}>
                Back
              </button>
              <button
                type="button"
                className="inline-confirm-btn"
                disabled={!newName.trim() || createCustomer.isPending}
                onClick={handleAdd}
              >
                {createCustomer.isPending ? "Adding…" : "Add & select"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
