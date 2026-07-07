import { useAuth } from "../context/AuthContext";

// Deliberate stub for the authenticated landing route. Which screen a
// user lands on post-login (POS for cashiers, dashboard for
// manager/owner per design doc navigation) is a future session's
// decision once those screens exist -- this just proves the auth flow
// end-to-end (login -> token stored -> /auth/me/ restores session ->
// protected route renders).
export default function HomePlaceholder() {
  const { user, logout } = useAuth();

  return (
    <div style={{ maxWidth: 480, margin: "80px auto", padding: 24, textAlign: "center" }}>
      <h1 style={{ fontSize: 20 }}>Signed in as {user?.name}</h1>
      <p style={{ color: "var(--color-text-secondary)", fontSize: 14 }}>
        Role: {user?.role} · {user?.branch?.business_name}
      </p>
      <p style={{ color: "var(--color-text-tertiary)", fontSize: 13 }}>
        POS / dashboard screens are built in future sessions.
      </p>
      <button
        type="button"
        onClick={() => logout()}
        style={{
          marginTop: 16,
          padding: "8px 16px",
          borderRadius: "var(--border-radius-md)",
          border: "0.5px solid var(--color-border-secondary)",
          background: "#fff",
          cursor: "pointer",
        }}
      >
        Sign out
      </button>
    </div>
  );
}
