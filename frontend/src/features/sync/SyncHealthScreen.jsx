import { useAuth } from "../../context/AuthContext";
import Banner from "../../components/Banner";
import ScreenTopbar from "../../components/ScreenTopbar";
import { useSyncHealth } from "../../hooks/useSyncStatus";
import "./SyncHealthScreen.css";

// Owner sync-health view (Phase 2 design §2.6). Rejected outbox entries are
// silent data loss unless someone can see them — this is where the owner
// does. Pending backlog + last-contact state sit on top; the device's own
// health only (per-branch, cross-branch last-seen is the HQ dashboard, step
// 14). Owner-gating is the route's RoleGuard; the endpoint is IsOwner too.

function formatWhen(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString([], {
    year: "numeric", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit", hour12: false,
  });
}

const OP_LABEL = { insert: "Insert", update: "Update", delete: "Delete" };

export default function SyncHealthScreen() {
  const { user } = useAuth();
  const { data, isLoading, isError } = useSyncHealth();

  const pending = data?.pending ?? 0;
  const rejectedCount = data?.rejected_count ?? 0;
  const failures = data?.consecutive_failures ?? 0;
  const rejected = data?.rejected ?? [];

  return (
    <div className="synch-page">
      <div className="synch-screen">
        <ScreenTopbar
          title="Bledger"
          badge="Sync health"
          meta={<span>🔄 {user?.name} · {user?.branch?.branch_name}</span>}
        />

        {isError && (
          <Banner type="error">Couldn&apos;t load sync health. Check your connection.</Banner>
        )}

        {!isError && (
          <div className="synch-body">
            <div className="synch-summary">
              <div className="synch-stat">
                <div className={`synch-stat-value${pending > 0 ? " warn" : ""}`}>{pending}</div>
                <div className="synch-stat-label">Changes waiting to sync</div>
              </div>
              <div className="synch-stat">
                <div className={`synch-stat-value${rejectedCount > 0 ? " err" : ""}`}>
                  {rejectedCount}
                </div>
                <div className="synch-stat-label">Rejected (need attention)</div>
              </div>
              <div className="synch-stat">
                <div className={`synch-stat-value${failures > 0 ? " err" : ""}`}>
                  {failures > 0 ? "Offline" : "OK"}
                </div>
                <div className="synch-stat-label">
                  {failures > 0
                    ? `${failures} failed attempt${failures === 1 ? "" : "s"}`
                    : "Connection"}
                </div>
              </div>
              <div className="synch-stat">
                <div className="synch-stat-value" style={{ fontSize: "0.95rem" }}>
                  {formatWhen(data?.last_success_at)}
                </div>
                <div className="synch-stat-label">Last successful sync</div>
              </div>
            </div>

            <div className="synch-content">
              {data?.last_error && failures > 0 && (
                <Banner type="warning">Last sync error: {data.last_error}</Banner>
              )}

              <div className="synch-section-title">Rejected changes</div>
              {isLoading ? (
                <div className="synch-empty">Loading sync health…</div>
              ) : rejected.length === 0 ? (
                <div className="synch-empty">
                  No rejected changes. Everything the branch has recorded is
                  either synced or waiting to sync.
                </div>
              ) : (
                <table className="synch-table">
                  <thead>
                    <tr>
                      <th>Rejected</th>
                      <th>Table</th>
                      <th>Operation</th>
                      <th>Reason</th>
                      <th>Tries</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rejected.map((r) => (
                      <tr key={r.id}>
                        <td>{formatWhen(r.rejected_at)}</td>
                        <td>{r.table_name}</td>
                        <td>{OP_LABEL[r.operation] ?? r.operation}</td>
                        <td className="synch-reason">{r.last_error || "—"}</td>
                        <td>{r.attempted}</td>
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
