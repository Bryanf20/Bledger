import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import { useSetupStatus } from "./hooks/useSetupStatus";
import RoleGuard from "./components/RoleGuard";
import NavRail from "./components/NavRail";
import LoginScreen from "./features/auth/LoginScreen";
import SetupWizard from "./features/setup/SetupWizard";
import HomePlaceholder from "./features/HomePlaceholder";
import POSScreen from "./features/pos/POSScreen";
import ReceiptScreen from "./features/receipt/ReceiptScreen";
import InventoryScreen from "./features/inventory/InventoryScreen";
import SalesHistoryScreen from "./features/sales/SalesHistoryScreen";
import SuppliersScreen from "./features/suppliers/SuppliersScreen";
import CustomersScreen from "./features/customers/CustomersScreen";
import DashboardScreen from "./features/dashboard/DashboardScreen";

function FullPageLoader() {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh" }}>
      Loading…
    </div>
  );
}

function RequireSetupComplete({ children }) {
  const { data, isLoading, isError } = useSetupStatus();

  if (isLoading) return <FullPageLoader />;
  if (isError) return children;
  if (!data?.setup_complete) return <Navigate to="/setup" replace />;

  return children;
}

// Inverse guard for /setup itself: once a Branch with setup_complete
// is already true, POST /setup/ returns 409 (see SetupView) -- so
// there's no point letting anyone land on the wizard for an install
// that's already set up.
function RequireSetupIncomplete({ children }) {
  const { data, isLoading, isError } = useSetupStatus();

  if (isLoading) return <FullPageLoader />;
  if (isError) return children;
  if (data?.setup_complete) return <Navigate to="/login" replace />;

  return children;
}

function RequireAuth({ children }) {
  const { isAuthenticated, isRestoring } = useAuth();

  if (isRestoring) return <FullPageLoader />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;

  return children;
}

export default function App() {
  // isAuthenticated gates NavRail globally here rather than each
  // screen importing it individually -- NavRail is `position: fixed`
  // (see its own header comment) so it renders as a sibling of
  // <Routes>, not inside any one screen's component tree. isRestoring
  // is intentionally NOT checked here: on a hard refresh the very
  // first render has isAuthenticated=false before the token restore
  // resolves, which would flash the rail in then out. Waiting for
  // RequireAuth's own loader to resolve first (which every protected
  // route already goes through) means the rail only appears once
  // there's a real, settled session, no flash either way.
  const { isAuthenticated, isRestoring } = useAuth();
  const showNavRail = isAuthenticated && !isRestoring;

  return (
    <>
      {showNavRail && <NavRail />}
      <Routes>
        <Route
          path="/setup"
          element={
            <RequireSetupIncomplete>
              <SetupWizard />
            </RequireSetupIncomplete>
          }
        />
        <Route
          path="/login"
          element={
            <RequireSetupComplete>
              <LoginScreen />
            </RequireSetupComplete>
          }
        />
        <Route
          path="/"
          element={
            <RequireSetupComplete>
              <RequireAuth>
                <HomePlaceholder />
              </RequireAuth>
            </RequireSetupComplete>
          }
        />
        <Route
          path="/pos"
          element={
            <RequireSetupComplete>
              <RequireAuth>
                <POSScreen />
              </RequireAuth>
            </RequireSetupComplete>
          }
        />
        <Route
          path="/receipt/:id"
          element={
            <RequireSetupComplete>
              <RequireAuth>
                <ReceiptScreen />
              </RequireAuth>
            </RequireSetupComplete>
          }
        />
        <Route
          path="/inventory"
          element={
            <RequireSetupComplete>
              <RequireAuth>
                <InventoryScreen />
              </RequireAuth>
            </RequireSetupComplete>
          }
        />
        <Route
          path="/sales"
          element={
            <RequireSetupComplete>
              <RequireAuth>
                <SalesHistoryScreen />
              </RequireAuth>
            </RequireSetupComplete>
          }
        />
        {/* Customers are cashier-visible (select at POS, record payments);
            only credit-limit edits are manager-gated, enforced inside the
            screen + the API rather than by a RoleGuard on the route. */}
        <Route
          path="/customers"
          element={
            <RequireSetupComplete>
              <RequireAuth>
                <CustomersScreen />
              </RequireAuth>
            </RequireSetupComplete>
          }
        />
        {/* Manager+ only, per apps/suppliers/views.py's IsManagerOrOwner
            gate on the whole backend app -- RoleGuard redirects a
            cashier straight to /pos rather than letting them land on a
            screen that would just error on every request. NavRail
            already hides the nav item for cashiers; this route guard
            is what stops a cashier who types the URL directly. */}
        <Route
          path="/suppliers"
          element={
            <RequireSetupComplete>
              <RequireAuth>
                <RoleGuard minimumRole="manager" redirectTo="/pos">
                  <SuppliersScreen />
                </RoleGuard>
              </RequireAuth>
            </RequireSetupComplete>
          }
        />
        {/* NOT wrapped in RoleGuard, unlike /suppliers -- see
            DashboardScreen's own header comment (built last session):
            StockAlertView is IsCashierOrAbove while every other
            dashboard endpoint is IsManagerOrOwner, and the UI Design
            Reference calls out stock alerts as the one cashier-visible
            widget. NavRail hides the *nav entry point* for cashiers
            (matching the doc's global "Dashboard navigation entirely
            (cashiers don't see it)" line) without blocking the route
            itself, so a cashier who does land here (e.g. a bookmarked
            URL) still gets the cashier-limited view rather than a
            bounce to /pos. */}
        <Route
          path="/dashboard"
          element={
            <RequireSetupComplete>
              <RequireAuth>
                <DashboardScreen />
              </RequireAuth>
            </RequireSetupComplete>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}
