import { createContext, useContext } from "react";

// Context object + consumer hook only; the provider lives in
// ThemeProvider.jsx. Keeps this file free of component exports for
// react-refresh's only-export-components rule. Existing
// `import { useTheme } from "../context/ThemeContext"` keeps working.
export const ThemeContext = createContext(null);

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return ctx;
}
