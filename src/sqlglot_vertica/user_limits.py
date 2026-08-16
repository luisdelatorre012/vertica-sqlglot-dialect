"""Pure lexical validators for non-secret Vertica USER limits."""

from __future__ import annotations

import re

USER_INTERVAL_MAX_SECONDS = {
    "GRACEPERIOD": 20 * 86_400,
    "IDLESESSIONTIMEOUT": 365 * 86_400,
    "RUNTIMECAP": 365 * 86_400,
}

_SECOND = 1_000_000
_UNIT_MICROSECONDS = {
    "D": 86_400 * _SECOND,
    "DAY": 86_400 * _SECOND,
    "DAYS": 86_400 * _SECOND,
    "H": 3_600 * _SECOND,
    "HOUR": 3_600 * _SECOND,
    "HOURS": 3_600 * _SECOND,
    "HR": 3_600 * _SECOND,
    "HRS": 3_600 * _SECOND,
    "M": 60 * _SECOND,
    "MIN": 60 * _SECOND,
    "MINS": 60 * _SECOND,
    "MINUTE": 60 * _SECOND,
    "MINUTES": 60 * _SECOND,
    "MON": 30 * 86_400 * _SECOND,
    "MONS": 30 * 86_400 * _SECOND,
    "MONTH": 30 * 86_400 * _SECOND,
    "MONTHS": 30 * 86_400 * _SECOND,
    "MS": 1_000,
    "MSEC": 1_000,
    "MSECS": 1_000,
    "MSECOND": 1_000,
    "MSECONDS": 1_000,
    "MILLISECOND": 1_000,
    "MILLISECONDS": 1_000,
    "S": _SECOND,
    "SEC": _SECOND,
    "SECS": _SECOND,
    "SECOND": _SECOND,
    "SECONDS": _SECOND,
    "US": 1,
    "USEC": 1,
    "USECS": 1,
    "USECOND": 1,
    "USECONDS": 1,
    "MICROSECOND": 1,
    "MICROSECONDS": 1,
    "W": 7 * 86_400 * _SECOND,
    "WEEK": 7 * 86_400 * _SECOND,
    "WEEKS": 7 * 86_400 * _SECOND,
    "Y": 365 * 86_400 * _SECOND,
    "YEAR": 365 * 86_400 * _SECOND,
    "YEARS": 365 * 86_400 * _SECOND,
    "YR": 365 * 86_400 * _SECOND,
    "YRS": 365 * 86_400 * _SECOND,
}
_UNIT_PATTERN = "|".join(sorted(_UNIT_MICROSECONDS, key=len, reverse=True))
_COMPONENT_RE = re.compile(rf"(\d+)\s*({_UNIT_PATTERN})", re.IGNORECASE | re.ASCII)
_COLON_RE = re.compile(r"(?:(\d+)\s+)?(\d+):(\d+)(?::(\d+)(?:\.(\d{1,6}))?)?", re.ASCII)


def _bounded_digits_value(digits: str, maximum: int) -> int | None:
    normalized = digits.lstrip("0") or "0"
    maximum_text = str(maximum)
    if (len(normalized), normalized) > (len(maximum_text), maximum_text):
        return None
    return int(normalized)


def _add_component(total: int, digits: str, multiplier: int, maximum: int) -> int | None:
    remaining = maximum - total
    value = _bounded_digits_value(digits, remaining // multiplier)
    return None if value is None else total + value * multiplier


def user_interval_at_most(value: str, maximum_seconds: int) -> bool:
    """Return whether a pinned, nonnegative Vertica interval fits the USER limit."""

    if not value or not value.isascii() or value != value.strip():
        return False
    maximum = maximum_seconds * _SECOND

    colon = _COLON_RE.fullmatch(value)
    if colon:
        days, hours, minutes, seconds, fraction = colon.groups()
        if _bounded_digits_value(minutes, 59) is None:
            return False
        if seconds is not None and _bounded_digits_value(seconds, 59) is None:
            return False
        if days is not None and _bounded_digits_value(hours, 23) is None:
            return False
        total = 0
        for digits, multiplier in (
            (days, 86_400 * _SECOND),
            (hours, 3_600 * _SECOND),
            (minutes, 60 * _SECOND),
            (seconds, _SECOND),
        ):
            if digits is not None:
                added = _add_component(total, digits, multiplier, maximum)
                if added is None:
                    return False
                total = added
        if fraction:
            total += int(fraction.ljust(6, "0"))
        return total <= maximum

    if value.isdigit():
        return _add_component(0, value, 86_400 * _SECOND, maximum) is not None

    total = 0
    position = 0
    matched = False
    for component in _COMPONENT_RE.finditer(value):
        if component.start() != position and value[position : component.start()].strip():
            return False
        if matched and not value[position : component.start()]:
            return False
        digits, unit = component.groups()
        added = _add_component(total, digits, _UNIT_MICROSECONDS[unit.upper()], maximum)
        if added is None:
            return False
        total = added
        position = component.end()
        matched = True
    return matched and position == len(value)


def canonical_user_capacity(value: str) -> str | None:
    """Validate and canonicalize a quoted percentage or K/M/G/T USER cap."""

    match = re.fullmatch(r"(\d+)(%|[KMGT])", value, re.IGNORECASE | re.ASCII)
    if not match:
        return None
    digits, suffix = match.groups()
    if suffix == "%" and _bounded_digits_value(digits, 100) is None:
        return None
    return f"{digits}{suffix.upper()}"
