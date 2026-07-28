import { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import Banner from "../../components/Banner";
import ScreenTopbar from "../../components/ScreenTopbar";
import XAFAmount from "../../components/XAFAmount";
import { useHQSummary, useProvisionBranch } from "../../hooks/useHQ";
import { extractErrorMessage } from "../../api/errors";
import "./HQDashboardScreen.css";

// HQ multi-branch dashboard (Phase 2 design §2.4/§2.6) — the owner-facing
// payoff of the sync workstream: revenue and activity across every branch,
// with each branch's last-seen. Owner-only (RoleGuard on the route mirrors
// the IsOwner endpoint). On a single-branch/standalone install it simply
// shows the one branch.

const PERIODS = [
  { key: "today", label: "Today" },
  { key: "week", label: "This week" },
  { key: "month", label: "This month" },
];

function relativeTime(iso) {
  if (!iso) return "never";
  const secs = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (secs < 60) return "just now";
  const mins = Math.round(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}

// A branch that has never synced, or hasn't in over a day, is worth flagging.
function lastSeenClass(iso) {
  if (!iso) return "err";
  const hrs = (Date.now() - new Date(iso).getTime()) / 3_600_000;
  if (hrs > 24) return "err";
  if (hrs > 2) return "warn";
  return "ok";
}

export default function HQDashboardScreen() {
  const { user } = useAuth();
  const [period, setPeriod] = useState("today");
  const { data, isLoading, isError } = useHQSummary(period);

  // Branch provisioning (owner). `form` open state, and `issued` holds the
  // one-time enrolment code returned so it can be shown + copied once.
  const provision = useProvisionBranch();
  const [showForm, setShowForm] = useState(false);
  const [branchName, setBranchName] = useState("");
  const [branchCode, setBranchCode] = useState("");
  const [isHQ, setIsHQ] = useState(false);
  const [issued, setIssued] = useState(null);
  const [formError, setFormError] = useState(null);

  async function handleProvision(e) {
    e.preventDefault();
    setFormError(null);
    try {
      const result = await provision.mutateAsync({
        branch_name: branchName.trim(),
        code: branchCode.trim() || undefined,
        is_hq: isHQ,
      });
      setIssued(result);
      setShowForm(false);
      setBranchName("");
      setBranchCode("");
      setIsHQ(false);
    } catch (err) {
      setFormError(extractErrorMessage(err, "Couldn\u2019t create the branch."));
    }
  }

  const branches = data?.branches ?? [];

  return (
    <div className="hq-page">
      <div className="hq-screen">
        <ScreenTopbar
          title="Bledger"
          badge="Head office"
          meta={<span>🏢 {user?.name} · {user?.branch?.business_name}</span>}
        />

        {isError && (
          <Banner type="error">Couldn&apos;t load the head-office summary. Check your connection.</Banner>
        )}

        {!isError && (
          <div className="hq-body">
            <div className="hq-toolbar">
              <div className="hq-period-toggle">
                {PERIODS.map((p) => (
                  <div
                    key={p.key}
                    className={`hq-period-pill${period === p.key ? " active" : ""}`}
                    onClick={() => setPeriod(p.key)}
                  >
                    {p.label}
                  </div>
                ))}
              </div>
              <button
                type="button"
                className="hq-add-btn"
                onClick={() => { setShowForm((v) => !v); setIssued(null); setFormError(null); }}
              >
                + Add branch
              </button>
            </div>

            {issued && (
              <div className="hq-issued">
                <div className="hq-issued-title">
                  Branch “{issued.branch_name}” created ({issued.code})
                </div>
                <div className="hq-issued-row">
                  <span className="hq-issued-label">Enrolment code</span>
                  <code className="hq-issued-code">{issued.enrolment_code}</code>
                  <button
                    type="button"
                    className="hq-copy-btn"
                    onClick={() => navigator.clipboard?.writeText(issued.enrolment_code)}
                  >
                    Copy
                  </button>
                </div>
                <div className="hq-issued-hint">
                  On the new device run: <code>manage.py enrol_device --code {issued.enrolment_code}</code>
                  {" "}— or use the setup wizard&apos;s “Connect to head office”. One-time use; expires soon.
                </div>
              </div>
            )}

            {showForm && (
              <form className="hq-form" onSubmit={handleProvision}>
                <input
                  className="hq-input"
                  placeholder="Branch name (e.g. Limbe Branch)"
                  value={branchName}
                  onChange={(e) => setBranchName(e.target.value)}
                  required
                />
                <input
                  className="hq-input hq-input-code"
                  placeholder="Code (optional)"
                  value={branchCode}
                  onChange={(e) => setBranchCode(e.target.value.toUpperCase())}
                  maxLength={8}
                />
                <label className="hq-checkbox">
                  <input type="checkbox" checked={isHQ} onChange={(e) => setIsHQ(e.target.checked)} />
                  Head office
                </label>
                <button type="submit" className="hq-add-btn" disabled={provision.isPending || !branchName.trim()}>
                  {provision.isPending ? "Creating…" : "Create + get code"}
                </button>
                {formError && <span className="hq-form-error">{formError}</span>}
              </form>
            )}

            <div className="hq-stats">
              <div className="hq-stat">
                <div className="hq-stat-value">
                  <XAFAmount value={data?.total_revenue ?? 0} />
                </div>
                <div className="hq-stat-label">Total revenue (all branches)</div>
              </div>
              <div className="hq-stat">
                <div className="hq-stat-value">{data?.total_transactions ?? 0}</div>
                <div className="hq-stat-label">Transactions</div>
              </div>
              <div className="hq-stat">
                <div className="hq-stat-value">{data?.branch_count ?? 0}</div>
                <div className="hq-stat-label">Branches</div>
              </div>
            </div>

            <div className="hq-content">
              {isLoading ? (
                <div className="hq-empty">Loading branches…</div>
              ) : branches.length === 0 ? (
                <div className="hq-empty">No branches yet.</div>
              ) : (
                <table className="hq-table">
                  <thead>
                    <tr>
                      <th>Branch</th>
                      <th>Code</th>
                      <th className="hq-num">Revenue</th>
                      <th className="hq-num">Sales</th>
                      <th>Last synced</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {branches.map((b) => (
                      <tr key={b.branch_id}>
                        <td>
                          {b.branch_name}
                          {b.is_hq && <span className="hq-tag">HQ</span>}
                        </td>
                        <td>{b.code ?? "—"}</td>
                        <td className="hq-num">
                          <XAFAmount value={b.revenue} />
                        </td>
                        <td className="hq-num">{b.transaction_count}</td>
                        <td>
                          <span className={`hq-lastseen hq-lastseen-${lastSeenClass(b.last_synced_at)}`}>
                            {relativeTime(b.last_synced_at)}
                          </span>
                        </td>
                        <td>
                          {b.is_active ? (
                            <span className="hq-status-active">Active</span>
                          ) : (
                            <span className="hq-status-inactive">Inactive</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
