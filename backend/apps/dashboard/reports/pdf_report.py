"""
Tabular PDF report generation, now that apps.printing exists.

Reuses apps.printing.pdf_backend.render_html_to_pdf() — the generic
HTML->PDF helper — rather than apps.printing.interface.print_receipt().
These are landscape A4 sales/products/stock reports, not 80mm receipts:
they don't use receipt.html and have no meaningful thermal-printer
rendering, so they intentionally bypass the backend-dispatch contract
built for receipts and go straight to the PDF engine.
"""
from django.http import HttpResponse
from django.utils.html import escape

from apps.printing.pdf_backend import PrinterDependencyMissing, render_html_to_pdf


class PdfReportNotReady(Exception):
    """Raised if the printing app's PDF engine isn't available on this install."""


def generate_pdf_report(filename, header, rows):
    html = _build_report_html(header, rows)
    try:
        pdf_bytes = render_html_to_pdf(html)
    except PrinterDependencyMissing as exc:
        raise PdfReportNotReady(str(exc))

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    pdf_filename = filename.rsplit(".", 1)[0] + ".pdf"
    response["Content-Disposition"] = f'attachment; filename="{pdf_filename}"'
    return response


def _build_report_html(header, rows):
    header_cells = "".join(f"<th>{escape(str(col))}</th>" for col in header)
    body_rows = "".join(
        "<tr>" + "".join(f"<td>{escape(str(cell))}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    return f"""
    <html><head><style>
      @page {{ size: A4 landscape; margin: 12mm; }}
      body {{ font-family: sans-serif; font-size: 10pt; }}
      table {{ width: 100%; border-collapse: collapse; }}
      th, td {{ border: 1px solid #ccc; padding: 4px 8px; text-align: left; }}
      th {{ background: #f2f2f2; }}
    </style></head>
    <body>
      <table><thead><tr>{header_cells}</tr></thead><tbody>{body_rows}</tbody></table>
    </body></html>
    """
