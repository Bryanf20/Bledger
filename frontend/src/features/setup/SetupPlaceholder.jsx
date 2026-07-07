// Deliberate stub. This session's scope is the scaffold + Login/PIN
// screen only (see project instructions -- setup wizard is the next
// natural frontend session, matching design doc B.7 / 07_setup_wizard.html).
// This placeholder exists so /setup is a real route that doesn't 404
// when useSetupStatus() reports setup_complete: false on a fresh
// install, rather than leaving a dead end in the router.
export default function SetupPlaceholder() {
  return (
    <div style={{ maxWidth: 480, margin: "80px auto", padding: 24, textAlign: "center" }}>
      <h1 style={{ fontSize: 20 }}>First-run setup</h1>
      <p style={{ color: "var(--color-text-secondary)", fontSize: 14 }}>
        This install hasn&apos;t been set up yet. The setup wizard (business details,
        product template, owner account) is built in a future session -- this route is a
        placeholder so the app doesn&apos;t dead-end here.
      </p>
    </div>
  );
}
