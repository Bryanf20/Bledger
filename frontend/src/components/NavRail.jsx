import { Link, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { hasRole } from "./RoleGuard";
import "./NavRail.css";

// Fixed-position rail, not a layout-wrapping component -- deliberately
// NOT restructuring App.jsx into nested routes with an <Outlet/>
// shell. Every screen's own .xxx-page div already owns a strict
// height:100vh -> min-height:0 chain (see screen-layout.css's header
// comment); wrapping that in a flex-row layout route risks that
// height:100vh no longer matching the actual viewport once a sibling
// nav column exists. Instead, NavRail is `position: fixed` (out of
// document flow) and rendered once here, at the App root, alongside
// <Routes> rather than inside any one screen. Room for it is made via
// `padding-left` (desktop) / `padding-bottom` (mobile) added to the
// shared .xxx-page group in screen-layout.css -- see this session's
// screen-layout.css patch. Every existing screen's internal layout is
// otherwise untouched.
//
// Role visibility resolves the tension between the UI Design
// Reference's two statements on Dashboard access: the global
// "Role-based visibility" pattern says "Dashboard navigation entirely
// (cashiers don't see it)", while Screen 5's own section says stock
// alerts are cashier-visible on the dashboard. Read together: cashiers
// get no *nav entry point* to Dashboard (this file), but the
// DashboardScreen route itself still renders a cashier-limited view
// if reached (built last session) rather than bouncing them away --
// the two statements aren't actually in conflict once "navigation"
// is read as "the nav link", not "the route".
const NAV_ITEMS = [
  { to: "/pos", label: "POS", icon: "🛒", minimumRole: "cashier" },
  { to: "/sales", label: "Sales", icon: "🧾", minimumRole: "cashier" },
  { to: "/inventory", label: "Inventory", icon: "📦", minimumRole: "cashier" },
  { to: "/suppliers", label: "Suppliers", icon: "🚚", minimumRole: "manager" },
  { to: "/dashboard", label: "Dashboard", icon: "📊", minimumRole: "manager" },
];

export default function NavRail() {
  const { role } = useAuth();
  const location = useLocation();

  const visibleItems = NAV_ITEMS.filter((item) => hasRole(role, item.minimumRole));

  return (
    <nav className="nav-rail" aria-label="Main navigation">
      <div className="nav-rail-brand">B</div>
      <div className="nav-rail-items">
        {visibleItems.map((item) => {
          // startsWith, not exact match -- /receipt/:id should still
          // highlight nothing (it's not a nav destination itself),
          // but a future nested path under e.g. /inventory/:id would
          // correctly keep Inventory highlighted.
          const active = location.pathname === item.to || location.pathname.startsWith(`${item.to}/`);
          return (
            <Link key={item.to} to={item.to} className={`nav-rail-item${active ? " active" : ""}`}>
              <span className="nav-rail-icon">{item.icon}</span>
              <span className="nav-rail-label">{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
