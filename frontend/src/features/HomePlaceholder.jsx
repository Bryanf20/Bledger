import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import ThemeToggle from "../components/ThemeToggle";

export default function HomePlaceholder() {
  const { user, logout } = useAuth();

  return (
    <div style={{ maxWidth: 480, margin: "80px auto", padding: 24, textAlign: "center" }}>
      <div style={{ display: "flex", justifyContent: "center", marginBottom: 24 }}>
        <ThemeToggle />
      </div>
      <h1 style={{ fontSize: 20 }}>Signed in as {user?.name}</h1>
      <p style={{ color: "var(--color-text-secondary)", fontSize: 14 }}>
        Role: {user?.role} · {user?.branch?.business_name}
      </p>
      <p style={{ color: "var(--color-text-tertiary)", fontSize: 13 }}>
        Sales history, Suppliers, and Dashboard screens are built in future sessions.
      </p>
      <div style={{ display: "flex", gap: 16, justifyContent: "center", marginBottom: 16 }}>
        <Link to="/pos">Go to POS</Link>
        <Link to="/inventory">Go to Inventory</Link>
      </div>
      <button
        type="button"
        onClick={() => logout()}
        style={{
          marginTop: 16,
          padding: "8px 16px",
          borderRadius: "var(--border-radius-md)",
          border: "0.5px solid var(--color-border-secondary)",
          background: "var(--color-background-primary)",
          color: "var(--color-text-primary)",
          cursor: "pointer",
        }}
      >
        Sign out
      </button>
    </div>
  );
}
