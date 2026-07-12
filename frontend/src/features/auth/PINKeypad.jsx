import "./LoginScreen.css";

const KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "", "0", "⌫"];

// Controlled component: `value` is the PIN digits typed so far (string,
// up to `length` chars), `onChange` receives the next value.
// Mirrors 06_login.html's .pin-display / .pin-keypad exactly (now
// login-pin-display / login-pin-keypad after this session's CSS
// prefix cleanup -- see LoginScreen.css's header comment).
export default function PINKeypad({ value, onChange, length = 4, disabled = false }) {
  function pressKey(key) {
    if (disabled) return;
    if (key === "⌫") {
      onChange(value.slice(0, -1));
      return;
    }
    if (key === "") return;
    if (value.length >= length) return;
    onChange(value + key);
  }

  return (
    <div>
      <div className="login-pin-display" role="status" aria-label={`${value.length} of ${length} digits entered`}>
        {Array.from({ length }).map((_, i) => (
          <div key={i} className={`login-pin-dot${i < value.length ? " filled" : ""}`} />
        ))}
      </div>
      <div className="login-pin-keypad">
        {KEYS.map((key, i) =>
          key === "" ? (
            <div key={i} />
          ) : (
            <button
              key={i}
              type="button"
              className="login-key"
              onClick={() => pressKey(key)}
              disabled={disabled}
              aria-label={key === "⌫" ? "Backspace" : `Digit ${key}`}
            >
              {key}
            </button>
          ),
        )}
      </div>
      <div className="login-pin-hint">4-digit PIN · fast access for cashiers</div>
    </div>
  );
}
