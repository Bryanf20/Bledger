import { useEffect, useRef } from "react";

// Detects a USB barcode scanner and reports the scanned code (Phase 2
// design §5.2). USB scanners are HID keyboard-emulation devices: they
// "type" the code far faster than any human and finish with Enter.
// We tell scanner from typist purely by speed — a burst of characters
// each arriving within `maxIntervalMs` of the last, terminated by Enter.
//
// Deliberately NOT a focused-input widget: the cashier should be able to
// scan at any moment on the POS without first clicking a field, so this
// is a global listener. The one accepted rough edge is that if a field
// happens to be focused mid-scan, the digits also land in it; the
// terminal Enter is consumed (preventDefault) once a scan is recognised,
// and a stray value in the search box simply matches nothing.
//
// Options:
//   onScan(code)   called with the decoded string on a completed scan.
//   enabled        set false to suspend detection (e.g. a modal is up,
//                  or the cashier toggled scanning off).
//   minLength      shortest burst treated as a scan (guards against a
//                  lone fast keypress plus Enter).
//   maxIntervalMs  max gap between keystrokes still counted as one burst.
export function useBarcodeInput({ onScan, enabled = true, minLength = 3, maxIntervalMs = 40 }) {
  // Keep the latest onScan in a ref so the effect doesn't re-subscribe
  // on every render (onScan is usually an inline arrow).
  const onScanRef = useRef(onScan);
  onScanRef.current = onScan;

  useEffect(() => {
    if (!enabled) return undefined;

    let buffer = "";
    let lastTime = 0;

    function handleKeydown(e) {
      // Ignore modifier combos — a scanner never sends them.
      if (e.ctrlKey || e.metaKey || e.altKey) return;

      const now = Date.now();

      if (e.key === "Enter") {
        // A fast burst of at least minLength chars ending in Enter is a
        // scan. Because any slow gap resets the buffer (below), reaching
        // minLength here guarantees the whole burst was fast.
        if (buffer.length >= minLength) {
          const code = buffer;
          buffer = "";
          e.preventDefault(); // don't let the scanner's Enter submit a form
          onScanRef.current?.(code);
          return;
        }
        buffer = "";
        return;
      }

      // Only single printable characters extend a barcode.
      if (e.key.length !== 1) return;

      // A gap larger than maxIntervalMs means this is the start of a new
      // sequence (or a human typing) — restart the buffer from this char.
      buffer = now - lastTime > maxIntervalMs ? e.key : buffer + e.key;
      lastTime = now;
    }

    window.addEventListener("keydown", handleKeydown);
    return () => window.removeEventListener("keydown", handleKeydown);
  }, [enabled, minLength, maxIntervalMs]);
}
