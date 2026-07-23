import { createContext, useContext } from "react";

// The context object + its consumer hook live here; the provider
// component lives in AuthProvider.jsx. Splitting them keeps this file
// free of component exports, which is what react-refresh's
// only-export-components rule wants (a file mixing a component and a
// hook breaks Fast Refresh). Every `import { useAuth } from
// "../context/AuthContext"` across the app keeps working unchanged.
export const AuthContext = createContext(null);

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
