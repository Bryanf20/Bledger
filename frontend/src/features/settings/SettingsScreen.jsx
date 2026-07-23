import { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import ScreenTopbar from "../../components/ScreenTopbar";
import ToastStack from "../../components/ToastStack";
import { useToasts } from "../../hooks/useToasts";
import BusinessTab from "./BusinessTab";
import PreferencesTab from "./PreferencesTab";
import StaffTab from "./StaffTab";
import "./SettingsScreen.css";

// Settings (Phase 2 §7.1–7.2 / step 8e). Owner-only — every underlying
// endpoint is IsOwner. One screen, three tabs (Business details, Policy
// preferences, Staff) rather than three nav items, keeping the rail
// short. The backends shipped in Stage 2; this is the frontend over them.
const TABS = [
  { key: "business", label: "Business" },
  { key: "preferences", label: "Preferences" },
  { key: "staff", label: "Staff" },
];

export default function SettingsScreen() {
  const { user } = useAuth();
  const [tab, setTab] = useState("business");
  const { toasts, showToast, dismissToast } = useToasts();

  const onSuccess = (m) => showToast("success", m);
  const onError = (m) => showToast("error", m);

  return (
    <div className="set-page">
      <div className="set-screen">
        <ScreenTopbar
          title="Bledger"
          badge="Settings"
          meta={<span>⚙️ {user?.name} · {user?.branch?.branch_name}</span>}
        />

        <div className="set-body">
          <div className="set-tabs">
            {TABS.map((t) => (
              <button
                key={t.key}
                type="button"
                className={`set-tab${tab === t.key ? " active" : ""}`}
                onClick={() => setTab(t.key)}
              >
                {t.label}
              </button>
            ))}
          </div>

          <div className="set-tab-content">
            {tab === "business" && <BusinessTab onSuccess={onSuccess} onError={onError} />}
            {tab === "preferences" && <PreferencesTab onSuccess={onSuccess} onError={onError} />}
            {tab === "staff" && <StaffTab onSuccess={onSuccess} onError={onError} />}
          </div>
        </div>
      </div>

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
