// Role hierarchy + check, extracted from RoleGuard.jsx so that file
// exports only its component (react-refresh only-export-components rule).
// Matches the backend's IsOwner / IsManagerOrOwner / IsCashierOrAbove
// permission classes (apps/core/permissions.py): owner > manager > cashier.
const ROLE_RANK = { cashier: 0, manager: 1, owner: 2 };

export function hasRole(userRole, minimumRole) {
  if (!userRole || !(userRole in ROLE_RANK)) return false;
  return ROLE_RANK[userRole] >= ROLE_RANK[minimumRole];
}
