import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import { useSetupStatus } from "./hooks/useSetupStatus";
import LoginScreen from "./features/auth/LoginScreen";
import SetupPlaceholder from "./features/setup/SetupPlaceholder";
import HomePlaceholder from "./features/HomePlaceholder";

function FullPageLoader() {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh" }}>
      Loading…
    </div>
  );
}

// Routing gate order matches the design doc's own priority: setup
// status gates everything (a fresh install must complete setup before
// anything else is reachable), then auth status gates the rest.
function RequireSetupComplete({ children }) {
  const { data, isLoading, isError } = useSetupStatus();

  if (isLoading) return <FullPageLoader />;
  // If the status check itself fails (backend unreachable), fail open
  // to the login screen rather than trapping the user on a loader --
  // the login/auth calls will surface the same connectivity error.
  if (isError) return children;
  if (!data?.setup_complete) return <Navigate to="/setup" replace />;

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
      <Route path="/setup" element={<SetupPlaceholder />} />
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
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
