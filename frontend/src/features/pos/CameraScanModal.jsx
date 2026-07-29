import { useEffect, useRef, useState } from "react";
import "./CameraScanModal.css";

// Camera barcode scanning at POS (Phase 2 design §5.3) — the follow-on to
// the USB scanner (§5.2). Uses the browser-native BarcodeDetector API: no
// dependency, good on the Android/Chrome hardware this targets. Falls back
// to a clear message where the API or a camera isn't available (older
// browsers, or an insecure/non-HTTPS context — getUserMedia needs one).
//
// It calls the SAME onScan the USB path uses, so all the product-resolution,
// stock checks and toasts are shared. It stays open for repeated scans (a
// till run is several items), debouncing the same code so one barcode held in
// frame isn't added on every frame.
const FORMATS = ["ean_13", "ean_8", "upc_a", "upc_e", "code_128", "code_39", "qr_code"];
const SCAN_INTERVAL_MS = 350;
const SAME_CODE_COOLDOWN_MS = 1500;

export default function CameraScanModal({ onScan, onClose }) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const lastCodeRef = useRef({ code: null, at: 0 });
  const [error, setError] = useState(null);

  useEffect(() => {
    const supported = typeof window !== "undefined" && "BarcodeDetector" in window;
    if (!supported) {
      setError(
        "Camera scanning isn’t supported on this device or browser. You can still use a USB scanner.",
      );
      return undefined;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("No camera access here — a secure (HTTPS) connection and a camera are required.");
      return undefined;
    }

    let cancelled = false;
    let intervalId;
    const detector = new window.BarcodeDetector({ formats: FORMATS });

    async function start() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "environment" },
          audio: false,
        });
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        const video = videoRef.current;
        if (video) {
          video.srcObject = stream;
          await video.play().catch(() => {});
        }

        intervalId = setInterval(async () => {
          const el = videoRef.current;
          if (!el || el.readyState < 2) return;
          let codes = [];
          try {
            codes = await detector.detect(el);
          } catch {
            return; // transient decode error — keep scanning
          }
          if (!codes.length) return;
          const code = codes[0].rawValue;
          const now = Date.now();
          const last = lastCodeRef.current;
          if (code === last.code && now - last.at < SAME_CODE_COOLDOWN_MS) return;
          lastCodeRef.current = { code, at: now };
          onScan(code);
        }, SCAN_INTERVAL_MS);
      } catch {
        if (!cancelled) setError("Couldn’t open the camera. Check permissions and try again.");
      }
    }
    start();

    return () => {
      cancelled = true;
      if (intervalId) clearInterval(intervalId);
      if (streamRef.current) streamRef.current.getTracks().forEach((t) => t.stop());
    };
  }, [onScan]);

  return (
    <div className="camscan-backdrop" onClick={onClose}>
      <div className="camscan-panel" onClick={(e) => e.stopPropagation()}>
        <div className="camscan-header">
          <span className="camscan-title">📷 Scan with camera</span>
          <button type="button" className="camscan-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        {error ? (
          <div className="camscan-error">{error}</div>
        ) : (
          <>
            <div className="camscan-video-wrap">
              <video ref={videoRef} className="camscan-video" muted playsInline />
              <div className="camscan-reticle" />
            </div>
            <div className="camscan-hint">
              Point the camera at a barcode. Items are added to the cart as they’re
              recognised — keep scanning, then close when done.
            </div>
          </>
        )}
      </div>
    </div>
  );
}
