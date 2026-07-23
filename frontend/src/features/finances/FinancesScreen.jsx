import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import ScreenTopbar from "../../components/ScreenTopbar";
import ToastStack from "../../components/ToastStack";
import Banner from "../../components/Banner";
import XAFAmount from "../../components/XAFAmount";
import { extractErrorMessage } from "../../api/errors";
import { useToasts } from "../../hooks/useToasts";
import {
  useCashbook,
  useCreateCashbookEntry,
  useDeleteCashbookEntry,
  useExpenseCategories,
  usePnl,
  useSeedDefaultCategories,
  useUpdateCashbookEntry,
} from "../../hooks/useFinances";
import "./FinancesScreen.css";

const PERIODS = [
  { key: "today", label: "Today" },
  { key: "week", label: "This week" },
  { key: "month", label: "This month" },
];

function todayISO() {
  // Local date, not UTC -- an expense recorded at 11pm belongs to today
  // for the shopkeeper, matching how the backend matches occurred_on.
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// Finances & cashbook (Phase 2 §7B). Manager+ records expenses/income and
// manages categories; the net-profit P&L is owner-only (gated on `role`
// here and by IsOwner on the endpoint). Whole screen is manager-gated by
// a RoleGuard on the route in App.jsx.
export default function FinancesScreen() {
  const { user } = useAuth();
  const [period, setPeriod] = useState("today");

  const { toasts, showToast, dismissToast } = useToasts();
  const { data: categories, isError: catError } = useExpenseCategories();
  const { data: entries, isLoading, isError } = useCashbook();
  // P&L relaxed to manager+ in step 8f (§7C.4) — same gate as the whole
  // screen, so it always loads for whoever reaches here.
  const { data: pnl, isLoading: pnlLoading } = usePnl(period);

  const seedDefaults = useSeedDefaultCategories();

  // On first visit with no categories, seed the standard set once so the
  // expense form has something to choose from. Idempotent server-side.
  useEffect(() => {
    if (categories && categories.length === 0 && !seedDefaults.isPending) {
      seedDefaults.mutate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [categories]);

  // Entries whose occurred_on falls in the selected period, newest first.
  const periodEntries = useMemo(() => {
    const list = entries ?? [];
    const [start, end] = periodBounds(period);
    return list
      .filter((e) => e.occurred_on >= start && e.occurred_on <= end)
      .sort((a, b) => (a.occurred_on < b.occurred_on ? 1 : -1));
  }, [entries, period]);

  return (
    <div className="fin-page">
      <div className="fin-screen">
        <ScreenTopbar
          title="Bledger — Finances"
          meta={<span>💰 {user?.name} · {user?.branch?.branch_name}</span>}
        />

        {(isError || catError) && (
          <Banner type="error">Couldn&apos;t load finances. Check your connection.</Banner>
        )}

        {!isError && (
          <div className="fin-body">
            <div className="fin-toolbar">
              <div className="fin-period-toggle">
                {PERIODS.map((p) => (
                  <button
                    key={p.key}
                    type="button"
                    className={`fin-period-pill${period === p.key ? " active" : ""}`}
                    onClick={() => setPeriod(p.key)}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </div>

            <PnLPanel pnl={pnl} isLoading={pnlLoading} />

            <div className="fin-columns">
              <RecordEntryForm
                categories={categories ?? []}
                onSuccess={(m) => showToast("success", m)}
                onError={(err, f) => showToast("error", extractErrorMessage(err, f))}
              />
              <CashbookLedger
                entries={periodEntries}
                isLoading={isLoading}
                onSuccess={(m) => showToast("success", m)}
                onError={(err, f) => showToast("error", extractErrorMessage(err, f))}
              />
            </div>
          </div>
        )}
      </div>

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}

// Local YYYY-MM-DD bounds for a period, matching the backend's
// today/week(Mon-based)/month spans closely enough for client filtering
// (the authoritative P&L numbers come from the server).
function periodBounds(period) {
  const now = new Date();
  const iso = (d) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  if (period === "today") return [iso(now), iso(now)];
  if (period === "week") {
    const day = (now.getDay() + 6) % 7; // Monday = 0
    const monday = new Date(now);
    monday.setDate(now.getDate() - day);
    return [iso(monday), iso(now)];
  }
  const first = new Date(now.getFullYear(), now.getMonth(), 1);
  return [iso(first), iso(now)];
}

function PnLPanel({ pnl, isLoading }) {
  if (isLoading || !pnl) {
    return (
      <div className="fin-pnl">
        <div className="fin-empty">Loading net profit…</div>
      </div>
    );
  }
  const net = pnl.net_profit;
  return (
    <div className="fin-pnl">
      <div className="fin-pnl-cards">
        <div className="fin-pnl-card">
          <div className="fin-pnl-label">Gross margin</div>
          <div className="fin-pnl-value"><XAFAmount value={pnl.gross_margin} /></div>
          <div className="fin-pnl-sub">Revenue − cost of goods</div>
        </div>
        <div className="fin-pnl-card">
          <div className="fin-pnl-label">− Expenses</div>
          <div className="fin-pnl-value danger"><XAFAmount value={pnl.total_expenses} /></div>
        </div>
        <div className="fin-pnl-card">
          <div className="fin-pnl-label">+ Other income</div>
          <div className="fin-pnl-value"><XAFAmount value={pnl.total_income} /></div>
        </div>
        <div className="fin-pnl-card net">
          <div className="fin-pnl-label">Net profit</div>
          <div className={`fin-pnl-value${net < 0 ? " danger" : " good"}`}><XAFAmount value={net} /></div>
        </div>
      </div>

      {pnl.expenses_by_category.length > 0 && (
        <div className="fin-breakdown">
          <div className="fin-section-title">Where the money went</div>
          <table className="fin-table">
            <thead><tr><th>Category</th><th className="num">Total</th></tr></thead>
            <tbody>
              {pnl.expenses_by_category.map((c) => (
                <tr key={c.category_id ?? "uncat"}>
                  <td>{c.category_name}</td>
                  <td className="num"><XAFAmount value={c.total} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function RecordEntryForm({ categories, onSuccess, onError }) {
  const createEntry = useCreateCashbookEntry();
  const [direction, setDirection] = useState("expense");
  const [categoryId, setCategoryId] = useState("");
  const [amount, setAmount] = useState("");
  const [occurredOn, setOccurredOn] = useState(todayISO());
  const [description, setDescription] = useState("");

  const activeCategories = categories.filter((c) => c.is_active);

  async function submit(e) {
    e.preventDefault();
    const amt = Number(amount);
    if (!amt || amt <= 0) return;
    const payload = {
      direction,
      amount: amt,
      occurred_on: occurredOn,
      description: description.trim(),
    };
    // Only expenses carry a category; the server rejects a category on
    // an income row (serializer.validate), so never send one.
    if (direction === "expense" && categoryId) payload.category = categoryId;
    try {
      await createEntry.mutateAsync(payload);
      setAmount("");
      setDescription("");
      onSuccess(direction === "expense" ? "Expense recorded." : "Income recorded.");
    } catch (err) {
      onError(err, "Couldn't save that entry.");
    }
  }

  return (
    <form className="fin-form" onSubmit={submit}>
      <div className="fin-section-title">Record an entry</div>

      <div className="fin-dir-toggle">
        <button
          type="button"
          className={`fin-dir-btn${direction === "expense" ? " active expense" : ""}`}
          onClick={() => setDirection("expense")}
        >
          Expense
        </button>
        <button
          type="button"
          className={`fin-dir-btn${direction === "income" ? " active income" : ""}`}
          onClick={() => setDirection("income")}
        >
          Other income
        </button>
      </div>

      {direction === "expense" && (
        <label className="fin-field">
          <span>Category</span>
          <select value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
            <option value="">Uncategorised</option>
            {activeCategories.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </label>
      )}

      <label className="fin-field">
        <span>Amount (XAF)</span>
        <input
          type="number"
          min="1"
          inputMode="numeric"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          placeholder="e.g. 50000"
          required
        />
      </label>

      <label className="fin-field">
        <span>Date</span>
        <input type="date" value={occurredOn} onChange={(e) => setOccurredOn(e.target.value)} required />
      </label>

      <label className="fin-field">
        <span>Note (optional)</span>
        <input
          type="text"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="e.g. July rent"
        />
      </label>

      <button type="submit" className="fin-submit" disabled={!amount || createEntry.isPending}>
        {createEntry.isPending ? "Saving…" : `Record ${direction === "expense" ? "expense" : "income"}`}
      </button>
    </form>
  );
}

function CashbookLedger({ entries, isLoading, onSuccess, onError }) {
  return (
    <div className="fin-ledger">
      <div className="fin-section-title">Cashbook</div>
      <div className="fin-ledger-scroll">
        {isLoading ? (
          <div className="fin-empty">Loading…</div>
        ) : entries.length === 0 ? (
          <div className="fin-empty">No entries in this period.</div>
        ) : (
          <table className="fin-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Detail</th>
                <th className="num">Amount</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => (
                <LedgerRow key={e.id} entry={e} onSuccess={onSuccess} onError={onError} />
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function LedgerRow({ entry, onSuccess, onError }) {
  const updateEntry = useUpdateCashbookEntry();
  const deleteEntry = useDeleteCashbookEntry();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(String(entry.amount));

  const isExpense = entry.direction === "expense";
  const detail = isExpense
    ? entry.category_name || "Uncategorised"
    : "Income";

  async function saveEdit() {
    const amt = Number(draft);
    if (!amt || amt <= 0) return;
    try {
      await updateEntry.mutateAsync({ id: entry.id, payload: { amount: amt } });
      setEditing(false);
      onSuccess("Entry updated.");
    } catch (err) {
      onError(err, "Couldn't update that entry.");
    }
  }

  async function remove() {
    try {
      await deleteEntry.mutateAsync(entry.id);
      onSuccess("Entry removed.");
    } catch (err) {
      onError(err, "Couldn't remove that entry.");
    }
  }

  return (
    <tr>
      <td>{entry.occurred_on}</td>
      <td>
        <span className={`fin-dir-tag ${isExpense ? "expense" : "income"}`}>{detail}</span>
        {entry.description ? <span className="fin-note"> · {entry.description}</span> : null}
      </td>
      <td className="num">
        {editing ? (
          <input
            type="number"
            min="1"
            className="fin-inline-input"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            autoFocus
          />
        ) : (
          <span className={isExpense ? "fin-amt-neg" : "fin-amt-pos"}>
            {isExpense ? "−" : "+"}<XAFAmount value={entry.amount} withSuffix={false} />
          </span>
        )}
      </td>
      <td className="fin-row-actions">
        {editing ? (
          <>
            <button type="button" className="fin-mini-btn" disabled={updateEntry.isPending} onClick={saveEdit}>Save</button>
            <button type="button" className="fin-mini-btn" onClick={() => { setEditing(false); setDraft(String(entry.amount)); }}>Cancel</button>
          </>
        ) : (
          <>
            <button type="button" className="fin-mini-btn" onClick={() => setEditing(true)}>Edit</button>
            <button type="button" className="fin-mini-btn danger" disabled={deleteEntry.isPending} onClick={remove}>Delete</button>
          </>
        )}
      </td>
    </tr>
  );
}
