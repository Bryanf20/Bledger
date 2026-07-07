import { useTheme } from "../context/ThemeContext";
import "./ThemeToggle.css";

// Icon shown is for the mode a click will switch TO, not the current
// mode -- light mode shows the moon (click for dark), dark mode shows
// the sun (click for light). `variant="on-brand"` is for placement on
// a navy/green brand surface (login left panel, wizard header) where
// the default border/text tokens would be invisible against a dark,
// theme-constant background.
const NEXT = {
  light: { icon: "🌙", label: "dark" },
  dark: { icon: "☀", label: "light" },
};

export default function ThemeToggle({ variant = "default" }) {
  const { theme, toggleTheme } = useTheme();
  const next = NEXT[theme];

  return (
    <button
      type="button"
      className={`theme-toggle-btn${variant === "on-brand" ? " on-brand" : ""}`}
      onClick={toggleTheme}
      title={`Switch to ${next.label} mode`}
      aria-label={`Switch to ${next.label} theme`}
    >
      <span aria-hidden="true">{next.icon}</span>
    </button>
  );
}
