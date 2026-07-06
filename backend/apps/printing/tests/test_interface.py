import pytest
from django.test import override_settings

from apps.printing.interface import UnknownPrinterBackend, print_receipt
from apps.printing.thermal_backend import ThermalBackendNotImplemented

MINIMAL_SALE_DATA = {
    "business_name": "Tabi Provisions",
    "branch_name": "Buea Main Branch",
    "address": "Molyko, Buea",
    "phone": "677123456",
    "receipt_footer": "",
    "date": "23/05/2026",
    "time": "14:32",
    "cashier_name": "Ambe J.",
    "sale_number": "0047",
    "reference": "BLD-2026-0047",
    "line_items": [{"name": "Mama Gold rice 5kg", "quantity": 2, "line_total": "9,000 XAF"}],
    "subtotal": "9,000 XAF",
    "tax_rate": "0%",
    "tax_amount": "0 XAF",
    "total_amount": "9,000 XAF",
    "payment_method": "Cash",
    "momo_reference": "",
}


def test_print_receipt_dispatches_to_pdf_backend_by_default():
    pdf_bytes = print_receipt(MINIMAL_SALE_DATA)
    assert pdf_bytes.startswith(b"%PDF")


@override_settings(PRINTER_BACKEND="thermal")
def test_print_receipt_dispatches_to_thermal_backend_when_configured():
    with pytest.raises(ThermalBackendNotImplemented):
        print_receipt(MINIMAL_SALE_DATA)


@override_settings(PRINTER_BACKEND="fax")
def test_unknown_backend_raises_clear_error():
    with pytest.raises(UnknownPrinterBackend):
        print_receipt(MINIMAL_SALE_DATA)
        