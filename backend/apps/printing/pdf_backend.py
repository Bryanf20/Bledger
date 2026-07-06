"""
Phase 1 printer backend (design doc 8.4). Renders the shared 80mm
`receipt.html` template to PDF bytes via WeasyPrint. thermal_backend.py
will reuse the same template in Phase 3 — the template, not this
module, is the thing shared between backends.

WeasyPrint is imported lazily/defensively: it depends on system
libraries (Pango, Cairo, GDK-PixBuf) that aren't always present on a
given machine, and a missing system lib should surface as a clear 503
("printing isn't available on this install"), not an ImportError at
Django startup that takes the whole project down.
"""
from django.template.loader import render_to_string

try:
    from weasyprint import HTML
except (ImportError, OSError):  # pragma: no cover - exercised only when
    HTML = None                  # WeasyPrint or its system libs are absent


class PrinterDependencyMissing(Exception):
    """Raised if WeasyPrint (or its system libraries) aren't available."""


def render_receipt(sale_data: dict) -> bytes:
    """Renders apps/printing/templates/receipt.html with sale_data as
    context and returns PDF bytes. sale_data is a plain dict built by
    the caller (see apps.sales.receipt_data.build_receipt_context())."""
    if HTML is None:
        raise PrinterDependencyMissing(_MISSING_DEPENDENCY_MESSAGE)
    html_string = render_to_string("receipt.html", sale_data)
    return HTML(string=html_string).write_pdf()


def render_html_to_pdf(html_string: str) -> bytes:
    """
    Low-level HTML->PDF helper. Not part of the print_receipt() contract
    — this is used by apps.dashboard's tabular report exports, which are
    landscape A4 reports, not 80mm receipts, so they don't go through
    receipt.html or backend dispatch (a thermal printer has no use for a
    sales/products/stock report). It's the one place in the project that
    knows how to turn arbitrary HTML into PDF bytes, reused rather than
    duplicated.
    """
    if HTML is None:
        raise PrinterDependencyMissing(_MISSING_DEPENDENCY_MESSAGE)
    return HTML(string=html_string).write_pdf()


_MISSING_DEPENDENCY_MESSAGE = (
    "WeasyPrint isn't installed, or its system libraries (Pango, Cairo, "
    "GDK-PixBuf) are missing on this machine. See "
    "https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation."
)
