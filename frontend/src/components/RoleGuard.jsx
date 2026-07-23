import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { hasRole } from "./roles";

// `hasRole` + the role hierarchy live in ./roles so this file exports
// only the RoleGuard component (react-refresh only-export-components).
// `allow` lists which roles may see the wrapped content; anyone else is
// redirected (default: to `redirectTo`, or rendered as `fallback` if
// provided instead of a redirect).
export default function RoleGuard({ allow, minimumRole, redirectTo = "/login", fallback = null, children }) {
  const { role, isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return fallback ?? <Navigate to={redirectTo} replace />;
  }

  const permitted = minimumRole ? hasRole(role, minimumRole) : allow?.includes(role);

  if (!permitted) {
    return fallback ?? null;
  }

  return children;
}
