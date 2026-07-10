import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import { useSetupStatus } from "./hooks/useSetupStatus";
import RoleGuard from "./components/RoleGuard";
import LoginScreen from "./features/auth/LoginScreen";
import SetupWizard from "./features/setup/SetupWizard";
import HomePlaceholder from "./features/HomePlaceholder";
import POSScreen from "./features/pos/POSScreen";
import ReceiptScreen from "./features/receipt/ReceiptScreen";
import InventoryScreen from "./features/inventory/InventoryScreen";
import SalesHistoryScreen from "./features/sales/SalesHistoryScreen";
import SuppliersScreen from "./features/suppliers/SuppliersScreen";

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
  return (
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
      {/* Manager+ only, per apps/suppliers/views.py's IsManagerOrOwner
          gate on the whole backend app -- RoleGuard redirects a
          cashier straight to /pos rather than letting them land on a
          screen that would just error on every request. This is the
          first route in the app to use RoleGuard as a route wrapper
          (existing screens like Receipt gate individual buttons
          in-component instead); Dashboard, built next, will need the
          same treatment. */}
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
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
