"""
Printer abstraction layer (design doc 8.4 / Part C).

print_receipt(sale_data) is the ONLY function the rest of the project
calls into this app. Callers (apps.sales today; apps.dashboard for its
own tabular PDFs uses pdf_backend.render_html_to_pdf() directly instead
— see that module's docstring) never talk to a backend module directly,
so switching PRINTER_BACKEND is a one-line settings change with zero
call-site changes.

sale_data is a plain dict, not a Sale model instance. This app never
imports apps.sales — callers build the dict themselves (see
apps.sales.receipt_data.build_receipt_context()) so apps.printing stays
a pure rendering layer with no dependency on any other app's models.
"""
from django.conf import settings

from . import pdf_backend, thermal_backend

BACKENDS = {
    "pdf": pdf_backend,
    "thermal": thermal_backend,
}


class UnknownPrinterBackend(Exception):
    """Raised when settings.PRINTER_BACKEND isn't a registered backend."""


def print_receipt(sale_data: dict) -> bytes:
    backend_name = getattr(settings, "PRINTER_BACKEND", "pdf")
    try:
        backend = BACKENDS[backend_name]
    except KeyError:
        raise UnknownPrinterBackend(
            f"PRINTER_BACKEND={backend_name!r} is not a recognised printer "
            f"backend. Valid options: {', '.join(BACKENDS)}."
        )
    return backend.render_receipt(sale_data)
