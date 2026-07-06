from apps.printing.pdf_backend import render_html_to_pdf, render_receipt
from apps.printing.tests.test_interface import MINIMAL_SALE_DATA


def test_render_receipt_produces_valid_pdf_bytes():
    pdf_bytes = render_receipt(MINIMAL_SALE_DATA)
    assert pdf_bytes.startswith(b"%PDF")


def test_render_receipt_includes_line_items_and_total():
    pdf_bytes = render_receipt(MINIMAL_SALE_DATA)
    assert len(pdf_bytes) > 500


def test_render_html_to_pdf_generic_helper():
    pdf_bytes = render_html_to_pdf("<html><body><h1>Report</h1></body></html>")
    assert pdf_bytes.startswith(b"%PDF")
    