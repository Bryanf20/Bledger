import { useEffect, useRef } from "react";
import { useSyncStatus } from "../hooks/useSyncStatus";
import { useToasts } from "../hooks/useToasts";
import ToastStack from "./ToastStack";

// App-root watcher that pops a transient toast when the branch reconnects
// or finishes flushing its backlog (Phase 2 design §2.6 "X changes synced").
// Mounted once alongside NavRail so the toast is screen-independent; it
// shares the single sync-status poll with the topbar badge (same query key).
export default function SyncToastHost() {
  const { data } = useSyncStatus();
  const { toasts, showToast, dismissToast } = useToasts();
  const prev = useRef(null);

  useEffect(() => {
    if (!data) return;
    const before = prev.current;
    prev.current = data;
    if (!before || !data.sync_enabled) return;

    // Transition into a healthy 'synced' from a non-synced state = we just
    // reconnected and/or drained the queue.
    const recovered = before.connectivity !== "synced" && data.connectivity === "synced";
    if (recovered) {
      const flushed = before.pending || 0;
      showToast(
        "success",
        flushed > 0
          ? `${flushed} change${flushed === 1 ? "" : "s"} synced`
          : "Back online — synced",
      );
    }
  }, [data, showToast]);

  return <ToastStack toasts={toasts} onDismiss={dismissToast} />;
}
