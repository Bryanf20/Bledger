// XAF has no subunit -- every monetary value from the API is already
// a whole-number integer (PositiveIntegerField server-side, per the
// locked architectural decision). This component only formats for
// display; it never rounds or does arithmetic, matching the backend's
// apps/core/utils/xaf.py being the single source of truth for
// rounding rules.
const formatter = new Intl.NumberFormat("en-US");

export default function XAFAmount({ value, withSuffix = true, className }) {
  if (value === null || value === undefined) {
    return <span className={className}>—</span>;
  }

  const formatted = formatter.format(value);
  return (
    <span className={className}>
      {formatted}
      {withSuffix ? " XAF" : ""}
    </span>
  );
}
