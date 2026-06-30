"""
XAF (Central African CFA franc) helpers.

XAF has no subunit in practical use — values are always whole numbers
(design doc Section 3 / 14). Every monetary field in the schema is an
integer; these helpers are the single place that formatting and
rounding rules live, so they never drift between screens.
"""
from decimal import ROUND_HALF_UP, Decimal


def round_xaf(amount) -> int:
    """Round any numeric amount to the nearest whole XAF."""
    return int(Decimal(str(amount)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def format_xaf(amount, *, with_suffix: bool = True) -> str:
    """
    Format a whole-number XAF amount with thousands separators.

    >>> format_xaf(1500000)
    '1,500,000 XAF'
    >>> format_xaf(1500000, with_suffix=False)
    '1,500,000'
    """
    value = round_xaf(amount)
    formatted = f"{value:,}"
    return f"{formatted} XAF" if with_suffix else formatted
