import "./Banner.css";

// Shared inline status banner -- unifies POS's .pos-error-banner /
// .pos-success-banner and Receipt's .receipt-error-banner, which were
// the same three rules (background/color/padding/radius) restated
// per screen. `type` is "error" | "success".
export default function Banner({ type = "error", children }) {
  return (
    <div className={`banner banner-${type}`} role={type === "error" ? "alert" : "status"}>
      {children}
    </div>
  );
}
