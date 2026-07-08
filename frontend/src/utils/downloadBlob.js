// Small shared helper: trigger a browser download for an in-memory
// Blob (e.g. a PDF fetched via axios with responseType: "blob")
// without navigating away or opening a new tab. The object URL is
// revoked right after the click, since by then the browser has
// already taken ownership of the download.
export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
