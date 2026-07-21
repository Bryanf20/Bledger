import { useEffect, useState } from "react";
import ThemeToggle from "./ThemeToggle";
import UserMenu from "./UserMenu";
import "./ScreenTopbar.css";

function formatClock(date) {
  // 24h HH:mm -- same convention as ReceiptScreen's formatTime()
  // (hour12: false), so the topbar and printed receipts agree.
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
}

// Minute-resolution live clock. First timeout lands exactly on the
// next minute boundary, then it ticks every 60s -- so the displayed
// minute is never stale, without a fast polling interval re-rendering
// the topbar for no visible change.
function TopbarClock() {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    let intervalId;
    const msToNextMinute = 60_000 - (Date.now() % 60_000);
    const timeoutId = setTimeout(() => {
      setNow(new Date());
      intervalId = setInterval(() => setNow(new Date()), 60_000);
    }, msToNextMinute);
    return () => {
      clearTimeout(timeoutId);
      if (intervalId) clearInterval(intervalId);
    };
  }, []);

  return (
    <span className="screen-topbar-clock" title={now.toLocaleDateString()}>
      🕐 {formatClock(now)}
    </span>
  );
}

// Shared topbar shell: title (+ optional badge pill) on the left,
// arbitrary meta content plus the always-present ThemeToggle/UserMenu
// pair on the right. Used by POSScreen and ReceiptScreen; any future
// screen (Inventory/Sales/Suppliers/Dashboard) should reuse this
// instead of restating the same title+meta+ThemeToggle+UserMenu row.
//
// `meta` is raw JSX, not a list -- each screen controls its own meta
// markup (POS's sync-dot span, Receipt's "user · branch" string)
// rather than ScreenTopbar imposing a wrapping convention on it.
export default function ScreenTopbar({ title, badge, meta }) {
  return (
    <div className="screen-topbar">
      <div className="screen-topbar-left">
        <span className="screen-topbar-title">{title}</span>
        {badge && <span className="screen-topbar-badge">{badge}</span>}
      </div>
      <div className="screen-topbar-meta">
        {meta}
        <TopbarClock />
        <ThemeToggle />
        <UserMenu />
      </div>
    </div>
  );
}
