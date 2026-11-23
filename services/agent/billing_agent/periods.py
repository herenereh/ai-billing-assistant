"""Billing-period helpers: month names (English and Turkish) and default periods."""

from __future__ import annotations

import re
from datetime import date

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

_ALIASES: dict[str, int] = {}
for _i, _en in enumerate(MONTH_NAMES, 1):
    _ALIASES[_en.lower()] = _i
    if _en != "May":
        _ALIASES[_en[:3].lower()] = _i
_ALIASES.pop("mar", None)  # "mar" is too ambiguous in short text; "march"/"mart" still work
for _i, _tr in enumerate(
    ["ocak", "şubat", "mart", "nisan", "mayıs", "haziran", "temmuz", "ağustos", "eylül", "ekim", "kasım", "aralık"], 1
):
    _ALIASES[_tr] = _i
_ALIASES.update({"sept": 9, "subat": 2, "mayis": 5, "agustos": 8, "eylul": 9, "kasim": 11, "aralik": 12})

_WORD = re.compile(r"[a-zçğıöşü]+")
_YEAR = re.compile(r"\b(20\d\d)\b")


def period_label(month: int, year: int) -> str:
    return f"{MONTH_NAMES[month - 1]} {year}"


def previous_period(month: int, year: int) -> tuple[int, int]:
    return (12, year - 1) if month == 1 else (month - 1, year)


def default_period(today: date) -> tuple[int, int]:
    """Most recent finished billing month (bills are calculated per calendar month)."""
    return previous_period(today.month, today.year)


def parse_period(text: str, today: date) -> tuple[int, int] | None:
    """Find a billing period in free text. Returns None when no month is mentioned."""
    lower = text.lower()
    if any(p in lower for p in ("this month", "bu ay", "my latest bill", "my last bill", "son fatura")):
        # The running month has no bill yet; "this month's bill" means the latest issued bill.
        return default_period(today)
    if any(p in lower for p in ("last month", "previous month", "geçen ay", "gecen ay")):
        return previous_period(today.month, today.year)
    month = None
    words = _WORD.findall(lower)
    for i, word in enumerate(words):
        # Turkish suffixes: "ekim'deki", "ekimdeki" → match on prefix for Turkish names
        candidate = _ALIASES.get(word) or next(
            (n for name, n in _ALIASES.items() if len(name) >= 4 and word.startswith(name)), None
        )
        if candidate is None:
            continue
        if word == "may" and not _is_month_may(words, i):
            continue
        month = candidate
        break
    if month is None:
        return None
    year_match = _YEAR.search(lower)
    if year_match:
        return month, int(year_match.group(1))
    # No year: the latest such month that is not in the future.
    return month, today.year if month <= today.month else today.year - 1


def _is_month_may(words: list[str], i: int) -> bool:
    """'may' is a month only in phrases like 'in may', 'may bill', 'may 2026'."""
    prev_word = words[i - 1] if i > 0 else ""
    next_word = words[i + 1] if i + 1 < len(words) else ""
    return prev_word in {"in", "for", "of"} or next_word in {"bill", "invoice", "usage", ""}
