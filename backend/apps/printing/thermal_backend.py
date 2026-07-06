"""
Phase 3 stub (design doc 8.4 / roadmap Section 12). Will use
python-escpos to translate the same receipt.html template into raw
ESC/POS commands for a USB/network thermal printer. Registered in
interface.BACKENDS now so PRINTER_BACKEND="thermal" is a valid,
recognised setting from day one — it just isn't functional until
Phase 3 lands.
"""


class ThermalBackendNotImplemented(Exception):
    """Raised until the Phase 3 ESC/POS backend is built."""


def render_receipt(sale_data: dict) -> bytes:
    raise ThermalBackendNotImplemented(
        "The thermal (ESC/POS) printer backend is Phase 3 scope and isn't "
        "implemented yet. Set PRINTER_BACKEND='pdf' in settings."
    )
