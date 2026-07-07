import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

const ThemeContext = createContext(null);

const STORAGE_KEY = "bledger_theme_preference";
const VALID_THEMES = ["light", "dark"];

function systemPrefersDark() {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

// System preference is only ever consulted once, as the default for a
// first-time visitor who hasn't chosen anything yet -- it is NOT a
// persistent third mode. Once a theme is stored, it's used verbatim
// forever until the person toggles again; there's no ongoing listener
// for OS-level theme changes, since "system" isn't a state this app
// tracks.
function resolveInitialTheme() {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (VALID_THEMES.includes(stored)) return stored;
  return systemPrefersDark() ? "dark" : "light";
}

// index.html runs a tiny inline script before this ever mounts, that
// reads the same localStorage key and the same system-preference
// fallback, and sets documentElement.dataset.theme synchronously --
// this context just takes over from there and keeps it in sync
// afterwards. Skipping that would mean a flash of the wrong theme on
// every load.
export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(resolveInitialTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  const setTheme = useCallback((next) => {
    if (!VALID_THEMES.includes(next)) return;
    localStorage.setItem(STORAGE_KEY, next);
    setThemeState(next);
  }, []);

  const toggleTheme = useCallback(() => {
    setTheme(theme === "dark" ? "light" : "dark");
  }, [theme, setTheme]);

  const value = useMemo(() => ({ theme, setTheme, toggleTheme }), [theme, setTheme, toggleTheme]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return ctx;
}
