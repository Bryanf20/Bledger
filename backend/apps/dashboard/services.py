"""
Period resolution for the dashboard app.

Every summary/aggregate endpoint in this app accepts ?period=today|week|month
(design doc B.5 / E.5). This module is the single place that turns that
query param into concrete datetime bounds.
"""
from datetime import timedelta

from django.utils import timezone

PERIOD_TODAY = "today"
PERIOD_WEEK = "week"
PERIOD_MONTH = "month"
VALID_PERIODS = (PERIOD_TODAY, PERIOD_WEEK, PERIOD_MONTH)


def resolve_period(period_param):
    """Normalizes the ?period= query param, defaulting to 'today' for
    anything missing or unrecognized rather than erroring — this is a
    dashboard convenience endpoint, not a strict API contract."""
    period = (period_param or PERIOD_TODAY).lower()
    if period not in VALID_PERIODS:
        period = PERIOD_TODAY
    return period


def period_range(period, now=None):
    """
    Returns (start, end) datetime bounds for the given period label.
    `end` is always "now"; `start` is midnight of today / the Monday of
    this week / the 1st of this month, in the current timezone.
    """
    now = now or timezone.localtime()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if period == PERIOD_WEEK:
        start = today_start - timedelta(days=today_start.weekday())  # Monday
    elif period == PERIOD_MONTH:
        start = today_start.replace(day=1)
    else:
        start = today_start

    return start, now


def previous_period_range(period, current_start, current_end):
    """
    Mirrors the current period immediately before it (same length), for
    the period-over-period deltas shown in the KPI strip (e.g. the design
    doc's "+12% vs yesterday" under the Revenue KPI).
    """
    span = current_end - current_start
    previous_end = current_start
    previous_start = previous_end - span
    return previous_start, previous_end
