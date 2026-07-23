import { useMemo, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { hasRole } from "../../components/roles";
import ScreenTopbar from "../../components/ScreenTopbar";
import ToastStack from "../../components/ToastStack";
import Banner from "../../components/Banner";
import XAFAmount from "../../components/XAFAmount";
import { extractErrorMessage } from "../../api/errors";
import { useToasts } from "../../hooks/useToasts";
import {
  useCustomers,
  useCreateCustomer,
  useUpdateCustomer,
  useRecordCustomerPayment,
} from "../../hooks/useCustomers";
import "./CustomersScreen.css";

// Customers & credit (Phase 2 §4). Master-detail like Suppliers, pointed
// the other way (money owed TO the shop). Reading, registering a
// customer, and recording a payment are cashier+; editing the credit
// limit is manager+ (enforced here and in the API).
export default function CustomersScreen() {
  const { user, role } = useAuth();
  const canEditLimit = hasRole(role, "manager");
  const { data: customers, isLoading, isError } = useCustomers();
  const createCustomer = useCreateCustomer();

  const { toasts, showToast, dismissToast } = useToasts();
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [adding, setAdding] = useState(false);
  const [newName, setNewName] = useState("");
  const [newPhone, setNewPhone] = useState("");

  const visible = useMemo(() => {
    const list = customers ?? [];
    const q = search.trim().toLowerCase();
    if (!q) return list;
    return list.filter((c) => c.name.toLowerCase().includes(q) || (c.phone || "").includes(q));
  }, [customers, search]);

  const selected = useMemo(() => {
    if (!customers?.length) return null;
    return customers.find((c) => c.id === selectedId) ?? customers[0];
  }, [customers, selectedId]);

  async function handleAdd() {
    if (!newName.trim()) return;
    try {
      const created = await createCustomer.mutateAsync({ name: newName.trim(), phone: newPhone.trim() });
      setSelectedId(created.id);
      setAdding(false);
      setNewName("");
      setNewPhone("");
      showToast("success", `${created.name} added.`);
    } catch (err) {
      showToast("error", extractErrorMessage(err, "Couldn't add that customer."));
    }
  }

  return (
    <div className="cust-page">
      <div className="cust-screen">
        <ScreenTopbar
          title="Bledger — Customers & credit"
          meta={<span>👤 {user?.name} · {user?.branch?.branch_name}</span>}
        />

        {isError && <Banner type="error">Couldn&apos;t load customers. Check your connection.</Banner>}

        {!isError && (
          <div className="cust-body">
            <div className="cust-list-panel">
              <div className="cust-list-header">
                <input
                  className="cust-search"
                  placeholder="Search name or phone…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
              <div className="cust-list-scroll">
                {isLoading ? (
                  <div className="cust-empty">Loading…</div>
                ) : visible.length === 0 ? (
                  <div className="cust-empty">{search ? "No matches." : "No customers yet."}</div>
                ) : (
                  visible.map((c) => (
                    <div
                      key={c.id}
                      className={`cust-item${selected?.id === c.id ? " active" : ""}`}
                      onClick={() => setSelectedId(c.id)}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && setSelectedId(c.id)}
                    >
                      <div className="cust-item-name">{c.name}</div>
                      <div className="cust-item-meta">
                        {c.phone || "No phone"} · owes <XAFAmount value={c.balance} />
                      </div>
                    </div>
                  ))
                )}
              </div>
              <div className="cust-list-footer">
                {!adding ? (
                  <button type="button" className="cust-add-btn" onClick={() => setAdding(true)}>
                    + Add customer
                  </button>
                ) : (
                  <div className="cust-add-form">
                    <input className="cust-search" placeholder="Name" value={newName} onChange={(e) => setNewName(e.target.value)} autoFocus />
                    <input className="cust-search" placeholder="Phone (optional)" value={newPhone} onChange={(e) => setNewPhone(e.target.value)} />
                    <div className="cust-add-actions">
                      <button type="button" className="cust-row-btn" onClick={() => setAdding(false)}>Cancel</button>
                      <button type="button" className="cust-confirm-btn" disabled={!newName.trim() || createCustomer.isPending} onClick={handleAdd}>
                        {createCustomer.isPending ? "Adding…" : "Add"}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>

            <CustomerDetail
              customer={selected}
              isLoading={isLoading}
              canEditLimit={canEditLimit}
              onSuccess={(m) => showToast("success", m)}
              onError={(err, f) => showToast("error", extractErrorMessage(err, f))}
            />
          </div>
        )}
      </div>

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}

function CustomerDetail({ customer, isLoading, canEditLimit, onSuccess, onError }) {
  const updateCustomer = useUpdateCustomer();
  const recordPayment = useRecordCustomerPayment();
  const [limitDraft, setLimitDraft] = useState(null);
  const [payAmount, setPayAmount] = useState("");

  if (isLoading) return <div className="cust-detail"><div className="cust-empty">Loading…</div></div>;
  if (!customer) return <div className="cust-detail"><div className="cust-empty">No customers yet — add one to record a credit sale.</div></div>;

  async function saveLimit() {
    try {
      await updateCustomer.mutateAsync({ id: customer.id, payload: { credit_limit: Number(limitDraft) || 0 } });
      setLimitDraft(null);
      onSuccess("Credit limit updated.");
    } catch (err) {
      onError(err, "Couldn't update the credit limit.");
    }
  }

  async function submitPayment() {
    const amount = Number(payAmount);
    if (!amount || amount <= 0) return;
    try {
      await recordPayment.mutateAsync({ customerId: customer.id, payload: { amount } });
      setPayAmount("");
      onSuccess(`Payment of ${amount} XAF recorded.`);
    } catch (err) {
      onError(err, "Couldn't record that payment.");
    }
  }

  const payments = customer.payments ?? [];

  return (
    <div className="cust-detail">
      <div className="cust-detail-header">
        <div>
          <div className="cust-detail-name">{customer.name}</div>
          <div className="cust-detail-meta">{customer.phone || "No phone"}{customer.area ? ` · ${customer.area}` : ""}</div>
        </div>
      </div>

      <div className="cust-stats">
        <div className="cust-stat">
          <div className="cust-stat-label">Owes now</div>
          <div className={`cust-stat-value${customer.balance > 0 ? " warning" : ""}`}><XAFAmount value={customer.balance} /></div>
        </div>
        <div className="cust-stat">
          <div className="cust-stat-label">Credit limit</div>
          <div className="cust-stat-value">
            {limitDraft === null ? (
              <span>
                <XAFAmount value={customer.credit_limit} />
                {canEditLimit && (
                  <button type="button" className="cust-row-btn cust-inline-btn" onClick={() => setLimitDraft(String(customer.credit_limit))}>Edit</button>
                )}
              </span>
            ) : (
              <span className="cust-limit-edit">
                <input type="number" min="0" className="cust-search" value={limitDraft} onChange={(e) => setLimitDraft(e.target.value)} autoFocus />
                <button type="button" className="cust-confirm-btn" disabled={updateCustomer.isPending} onClick={saveLimit}>Save</button>
                <button type="button" className="cust-row-btn" onClick={() => setLimitDraft(null)}>Cancel</button>
              </span>
            )}
          </div>
        </div>
        <div className="cust-stat">
          <div className="cust-stat-label">Remaining credit</div>
          <div className="cust-stat-value"><XAFAmount value={Math.max(customer.credit_limit - customer.balance, 0)} /></div>
        </div>
      </div>

      <div className="cust-detail-scroll">
        {customer.balance > 0 && (
          <div className="cust-payment-form">
            <div className="cust-payment-header">Record a payment</div>
            <div className="cust-payment-row">
              <input type="number" min="1" className="cust-search" placeholder="Amount received (XAF)" value={payAmount} onChange={(e) => setPayAmount(e.target.value)} />
              <button type="button" className="cust-confirm-btn" disabled={!payAmount || recordPayment.isPending} onClick={submitPayment}>
                {recordPayment.isPending ? "Recording…" : "Record payment"}
              </button>
            </div>
          </div>
        )}

        <div className="cust-section-title">Payment history</div>
        {payments.length === 0 ? (
          <div className="cust-empty">No payments recorded yet.</div>
        ) : (
          <table className="cust-table">
            <thead>
              <tr><th>Date</th><th>Method</th><th>Amount</th></tr>
            </thead>
            <tbody>
              {payments.map((p) => (
                <tr key={p.id}>
                  <td>{p.payment_date}</td>
                  <td>{p.payment_method}</td>
                  <td><XAFAmount value={p.amount} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
