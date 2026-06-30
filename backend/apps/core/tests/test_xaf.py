import pytest

from apps.core.utils.xaf import format_xaf, round_xaf


@pytest.mark.parametrize(
    "amount,expected",
    [
        (1500000, "1,500,000 XAF"),
        (0, "0 XAF"),
        (4500, "4,500 XAF"),
        (1500000.49, "1,500,000 XAF"),  # rounds, never shows decimals
        (1500000.5, "1,500,001 XAF"),
    ],
)
def test_format_xaf(amount, expected):
    assert format_xaf(amount) == expected


def test_format_xaf_without_suffix():
    assert format_xaf(4500, with_suffix=False) == "4,500"


def test_round_xaf_returns_int():
    assert round_xaf("4999.6") == 5000
    assert isinstance(round_xaf(100), int)
