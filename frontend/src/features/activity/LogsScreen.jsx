import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import Banner from "../../components/Banner";
import ScreenTopbar from "../../components/ScreenTopbar";
import { useActivity } from "../../hooks/useActivity";
import "./LogsScreen.css";

// Activity log (Phase 2 §7C.1 / step 8c). Read-only trail of the major
// things that happen in the branch. Managers see the key operational
// events; owners additionally see fine-grained detail — the split is
// server-enforced, this screen just renders whatever comes back. Sales
// are deliberately absent (they have their own history + receipts).

// Friendly labels + an icon per action key. Anything unmapped falls back
// to the raw key, so a newly-wired action still renders sanely.
const ACTION_META = {
  "auth.login": { label: "Sign-in", icon: "🔑" },
  "sale.void": { label: "Sale voided", icon: "↩️" },
  "expense.record": { label: "Expense recorded", icon: "💸" },
  "expense.edit": { label: "Expense edited", icon: "✏️" },
  "expense.delete": { label: "Expense deleted", icon: "🗑️" },
  "staff.create": { label: "Staff added", icon: "👤" },
  "staff.update": { label: "Staff updated", icon: "👤" },
  "staff.deactivate": { label: "Staff deactivated", icon: "🚫" },
  "staff.reset_pin": { label: "PIN reset", icon: "🔢" },
  "stock.adjust": { label: "Stock adjusted", icon: "📦" },
  "stock.loss_booked": { label: "Loss booked", icon: "📉" },
  "credit.limit_change": { label: "Credit limit", icon: "💳" },
  "settings.update": { label: "Settings changed", icon: "⚙️" },
  "product.create": { label: "Product added", icon: "🏷️" },
  "product.update": { label: "Product updated", icon: "🏷️" },
  "category.create": { label: "Category added", icon: "🗂️" },
  "supplier.create": { label: "Supplier added", icon: "🚚" },
  "purchase.record": { label: "Purchase recorded", icon: "🧾" },
};

// The filter dropdown — a curated subset of the major events.
const ACTION_FILTERS = [
  { key: "", label: "All activity" },
  { key: "auth.login", label: "Sign-ins" },
  { key: "sale.void", label: "Sale voids" },
  { key: "expense.record", label: "Expenses recorded" },
  { key: "stock.adjust", label: "Stock adjustments" },
  { key: "stock.loss_booked", label: "Losses booked" },
  { key: "credit.limit_change", label: "Credit-limit changes" },
  { key: "staff.create", label: "Staff added" },
  { key: "settings.update", label: "Settings changes" },
];

const PAGE_SIZE = 25; // apps.core.pagination.StandardResultsSetPagination

function formatWhen(iso) {
  const d = new Date(iso);
  return d.toLocaleString([], {
    year: "numeric", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit", hour12: false,
  });
}

export default function LogsScreen() {
  const { user, role } = useAuth();
  const [action, setAction] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    setPage(1);
  }, [action]);

  const filters = useMemo(() => ({ page, action: action || undefined }), [page, action]);
  const { data, isLoading, isError } = useActivity(filters);

  const rows = data?.results ?? [];
  const totalCount = data?.count ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));

  return (
    <div className="log-page">
      <div className="log-screen">
        <ScreenTopbar
          title="Bledger"
          badge="Activity log"
          meta={<span>📋 {user?.name} · {user?.branch?.branch_name}</span>}
        />

        {isError && <Banner type="error">Couldn&apos;t load the activity log. Check your connection.</Banner>}

        {!isError && (
          <div className="log-body">
            <div className="log-toolbar">
              <select className="log-select" value={action} onChange={(e) => setAction(e.target.value)}>
                {ACTION_FILTERS.map((f) => (
                  <option key={f.key} value={f.key}>{f.label}</option>
                ))}
              </select>
              <span className="log-scope-hint">
                {role === "owner"
                  ? "You see every logged event."
                  : "You see the key events; the owner sees full detail."}
              </span>
            </div>

            <div className="log-content">
              {isLoading ? (
                <div className="log-empty">Loading activity…</div>
              ) : rows.length === 0 ? (
                <div className="log-empty">No activity recorded yet.</div>
              ) : (
                <table className="log-table">
                  <thead>
                    <tr>
                      <th>When</th>
                      <th>Who</th>
                      <th>Event</th>
                      <th>Detail</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => {
                      const meta = ACTION_META[r.action] || { label: r.action, icon: "•" };
                      return (
                        <tr key={r.id}>
                          <td className="log-when">{formatWhen(r.created_at)}</td>
                          <td>{r.actor_name || "System"}</td>
                          <td>
                            <span className="log-event">
                              <span className="log-icon">{meta.icon}</span>
                              {meta.label}
                            </span>
                          </td>
                          <td className="log-detail">{r.summary}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>

            <div className="log-status-bar">
              <span>
                {totalCount === 0 ? "No events" : `Showing ${rows.length} of ${totalCount} events`}
              </span>
              <div className="log-pager">
                <button type="button" disabled={!data?.previous} onClick={() => setPage((p) => Math.max(1, p - 1))}>
                  ← Prev
                </button>
                <span>Page {page} of {totalPages}</span>
                <button type="button" disabled={!data?.next} onClick={() => setPage((p) => p + 1)}>
                  Next →
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
