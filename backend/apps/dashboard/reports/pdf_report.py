"""
PDF report generation is deferred to the `printing` app (next on the
build order after `dashboard`), which will provide the shared
`print_receipt()`-style interface used across the whole project.

This mirrors the interim pattern `apps.sales` already established for
`GET /sales/{id}/receipt/`: the route exists now so the frontend has a
stable integration point and doesn't need changes later, but it returns
503 until the printing app lands.
"""


class PdfReportNotReady(Exception):
    """Raised by generate_pdf_report() until apps.printing exists."""


def generate_pdf_report(filename, header, rows):
    raise PdfReportNotReady(
        "PDF export isn't available yet — it's pending the printing app. "
        "Use ?format=csv in the meantime."
    )
