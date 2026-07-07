import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

// Role hierarchy matches the backend's IsOwner / IsManagerOrOwner /
// IsCashierOrAbove permission classes (apps/core/permissions.py):
// owner > manager > cashier. `allow` lists which roles may see the
// wrapped content; anyone else is redirected (default: to `redirectTo`,
// or rendered as `fallback` if provided instead of a redirect).
const ROLE_RANK = { cashier: 0, manager: 1, owner: 2 };

export function hasRole(userRole, minimumRole) {
  if (!userRole || !(userRole in ROLE_RANK)) return false;
  return ROLE_RANK[userRole] >= ROLE_RANK[minimumRole];
}

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
