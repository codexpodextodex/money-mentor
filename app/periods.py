"""Turn period names such as "last_month" into date ranges.

All ranges are inclusive at both ends and never run past "today".
"""

from __future__ import annotations

import calendar
import datetime as dt
import re
from dataclasses import dataclass

PERIOD_NAMES = [
    "today",
    "yesterday",
    "this_week",
    "last_week",
    "this_month",
    "last_month",
    "last_7_days",
    "last_30_days",
    "last_90_days",
    "last_3_months",
    "last_6_months",
    "last_12_months",
    "this_year",
    "last_year",
    "all_time",
]


@dataclass(frozen=True)
class Period:
    start: dt.date
    end: dt.date
    label: str

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    @property
    def months(self) -> float:
        """Length in months, for monthly averages."""
        return self.days / 30.4375

    def previous(self) -> "Period":
        """The period of the same length just before this one."""
        if self.start.day == 1 and self.end == _month_end(self.end):
            n = (self.end.year - self.start.year) * 12 + self.end.month - self.start.month + 1
            prev_end = self.start - dt.timedelta(days=1)
            prev_start = _add_months(self.start, -n)
            return Period(prev_start, prev_end, "the period before")
        length = dt.timedelta(days=self.days)
        return Period(self.start - length, self.start - dt.timedelta(days=1), "the period before")

    def as_dict(self) -> dict:
        return {"start": self.start.isoformat(), "end": self.end.isoformat(), "label": self.label, "days": self.days}


def _month_start(d: dt.date) -> dt.date:
    return d.replace(day=1)


def _month_end(d: dt.date) -> dt.date:
    return d.replace(day=calendar.monthrange(d.year, d.month)[1])


def _add_months(d: dt.date, n: int) -> dt.date:
    index = d.year * 12 + (d.month - 1) + n
    year, month = index // 12, index % 12 + 1
    return dt.date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def _month_label(d: dt.date) -> str:
    return d.strftime("%B %Y")


def complete_months(today: dt.date, n: int) -> Period:
    """The n most recent calendar months that are fully over.

    The current month counts when today is its last day.
    """
    last_start = _month_start(today) if today == _month_end(today) else _add_months(_month_start(today), -1)
    start = _add_months(last_start, -(n - 1))
    end = _month_end(last_start)
    label = _month_label(start) if n == 1 else f"{start.strftime('%b %Y')} to {end.strftime('%b %Y')}"
    return Period(start, end, label)


def resolve(period: str | None, today: dt.date, start: str | None = None, end: str | None = None) -> Period:
    """Resolve a period name, a YYYY-MM month, a YYYY year or explicit dates."""
    if start or end:
        s = dt.date.fromisoformat(start) if start else dt.date(2000, 1, 1)
        e = min(dt.date.fromisoformat(end), today) if end else today
        if s > e:
            raise ValueError("start must not be after end")
        return Period(s, e, f"{s.isoformat()} to {e.isoformat()}")

    name = (period or "last_month").strip().lower().replace(" ", "_").replace("-", "_")
    weekday = today.weekday()  # Monday = 0

    if name == "today":
        return Period(today, today, "today")
    if name == "yesterday":
        y = today - dt.timedelta(days=1)
        return Period(y, y, "yesterday")
    if name == "this_week":
        return Period(today - dt.timedelta(days=weekday), today, "this week so far")
    if name == "last_week":
        s = today - dt.timedelta(days=weekday + 7)
        return Period(s, s + dt.timedelta(days=6), "last week")
    if name == "this_month":
        return Period(_month_start(today), today, _month_label(today))
    if name == "last_month":
        s = _add_months(_month_start(today), -1)
        return Period(s, _month_end(s), _month_label(s))
    match = re.fullmatch(r"last_(\d+)_days", name)
    if match:
        n = int(match.group(1))
        return Period(today - dt.timedelta(days=n - 1), today, f"the last {n} days")
    match = re.fullmatch(r"last_(\d+)_months", name)
    if match:
        return complete_months(today, int(match.group(1)))
    if name == "this_year":
        return Period(dt.date(today.year, 1, 1), today, f"{today.year} so far")
    if name == "last_year":
        return Period(dt.date(today.year - 1, 1, 1), dt.date(today.year - 1, 12, 31), str(today.year - 1))
    if name in ("all_time", "all", "ever"):
        return Period(dt.date(2000, 1, 1), today, "all time")
    match = re.fullmatch(r"(\d{4})_(\d{2})", name)
    if match:
        s = dt.date(int(match.group(1)), int(match.group(2)), 1)
        return Period(s, min(_month_end(s), today), _month_label(s))
    match = re.fullmatch(r"(\d{4})", name)
    if match:
        year = int(match.group(1))
        return Period(dt.date(year, 1, 1), min(dt.date(year, 12, 31), today), str(year))
    raise ValueError(f"Unknown period '{period}'. Use one of {', '.join(PERIOD_NAMES)}, a month like 2026-08, or start and end dates.")
