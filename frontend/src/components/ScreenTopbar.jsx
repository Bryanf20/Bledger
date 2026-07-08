import ThemeToggle from "./ThemeToggle";
import UserMenu from "./UserMenu";
import "./ScreenTopbar.css";

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
        <ThemeToggle />
        <UserMenu />
      </div>
    </div>
  );
}
