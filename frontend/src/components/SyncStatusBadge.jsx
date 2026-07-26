import { useSyncStatus } from "../hooks/useSyncStatus";
import "./SyncStatusBadge.css";

// The four connectivity states (Phase 2 design §2.6). "disabled" is the
// standalone case (no cloud at all) — shown muted as "Standalone", matching
// the login brand panel's "Standalone mode" line.
const STATE_META = {
  synced: { cls: "ok", label: "Synced" },
  syncing: { cls: "warn", label: "Syncing…" },
  offline: { cls: "err", label: "Offline" },
  disabled: { cls: "off", label: "Standalone" },
};

function relativeTime(iso) {
  if (!iso) return null;
  const then = new Date(iso).getTime();
  const secs = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (secs < 60) return "just now";
  const mins = Math.round(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}

// Live connectivity indicator in the topbar. Replaces the old hardcoded
// "Synced" dot. A failed poll is treated as offline (a branch that can't
// reach its own local API is, from the user's point of view, offline).
export default function SyncStatusBadge() {
  const { data, isError } = useSyncStatus();

  // Before the first poll resolves, render nothing rather than flashing a
  // wrong state into the topbar.
  if (!data && !isError) return null;

  let connectivity = data?.connectivity ?? "offline";
  if (isError) connectivity = "offline";
  const meta = STATE_META[connectivity] ?? STATE_META.synced;

  const pending = data?.pending ?? 0;
  let label = meta.label;
  if (connectivity === "syncing" && pending > 0) {
    label = `Syncing ${pending}`;
  }

  const lastSynced = relativeTime(data?.last_success_at);
  let title = meta.label;
  if (connectivity === "syncing") {
    title = `${pending} change${pending === 1 ? "" : "s"} waiting to sync`;
  } else if (connectivity === "offline") {
    title = lastSynced ? `Offline — last synced ${lastSynced}` : "Offline";
  } else if (connectivity === "synced") {
    title = lastSynced ? `Synced — last synced ${lastSynced}` : "Synced";
  } else if (connectivity === "disabled") {
    title = "Standalone install — no cloud sync";
  }

  return (
    <span className={`sync-badge sync-badge-${meta.cls}`} title={title}>
      <span className="sync-badge-dot" />
      <span className="sync-badge-label">{label}</span>
    </span>
  );
}
