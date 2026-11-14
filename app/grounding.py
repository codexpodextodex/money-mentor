"""Check that every number in an answer comes from a tool result.

The model explains; the engine computes. After the model writes its answer,
each number in the text is looked up among the numbers the tools returned
(and the numbers the user typed). A number that is found nowhere is flagged,
and the agent asks the model to rewrite the answer once.
"""

from __future__ import annotations

import json
import re

# 1,234.56  1 234,56  1234  12.5  0,5
_NUMBER = re.compile(r"(?<![\w.,])\d{1,3}(?:[   ,]\d{3})+(?:[.,]\d+)?|(?<![\w.,])\d+(?:[.,]\d+)?")
_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")

# Finnish and Swedish dates: 15.10. or 15.10.2026. Not a decimal number, so the
# day, month and year are checked as separate numbers. A currency sign before
# or a currency or percent sign after means it is an amount, not a date.
_DOTTED_DATE = re.compile(r"(?<![\w€$.,])([0-3]?\d)\.([01]?\d)\.(20\d{2})?(?!\d)(?!\s*(?:€|eur|%))", re.IGNORECASE)

# Counting words ("the 3 baskets", "2 changes") are not money claims.
SMALL_INTEGER_LIMIT = 12


def _split_dotted_dates(text: str) -> str:
    def parts(match: re.Match) -> str:
        day, month = int(match.group(1)), int(match.group(2))
        if 1 <= day <= 31 and 1 <= month <= 12:
            # Semicolons keep the parts apart: "10 2026" would read as a spaced thousand.
            return f" {day} ; {month} ; {match.group(3) or ''} ; "
        return match.group(0)

    return _DOTTED_DATE.sub(parts, text)


def parse_number(text: str) -> float | None:
    s = text.replace(" ", "").replace(" ", "").replace(" ", "")
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        head, _, tail = s.rpartition(",")
        s = s.replace(",", "") if len(tail) == 3 and head else s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def numbers_in_text(text: str) -> list[tuple[str, float]]:
    cleaned = _split_dotted_dates(_DATE.sub(" ", text or ""))
    found = []
    for match in _NUMBER.finditer(cleaned):
        value = parse_number(match.group(0))
        if value is not None:
            found.append((match.group(0), value))
    return found


def numbers_in_data(data) -> set[float]:
    """Every number in a tool result, including those inside its strings."""
    out: set[float] = set()

    def walk(node) -> None:
        if isinstance(node, bool) or node is None:
            return
        if isinstance(node, (int, float)):
            out.add(abs(float(node)))
        elif isinstance(node, str):
            for part in re.split(r"[-:T/]", node) if _DATE.search(node) else [node]:
                for _, value in numbers_in_text(part):
                    out.add(abs(value))
        elif isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, (list, tuple)):
            for value in node:
                walk(value)

    walk(data)
    return out


def _matches(value: float, sources: set[float]) -> bool:
    for s in sources:
        # Equal after rounding to whole euros or whole percent, or within half a percent.
        if abs(value - s) <= max(0.51, 0.005 * s):
            return True
    return False


def check(answer: str, tool_results: list, question: str = "") -> dict:
    """Return which numbers in the answer could not be traced to a tool result."""
    sources: set[float] = set()
    for result in tool_results:
        sources |= numbers_in_data(result)
    sources |= {abs(v) for _, v in numbers_in_text(question)}

    unverified, checked = [], 0
    for raw, value in numbers_in_text(answer):
        if value <= SMALL_INTEGER_LIMIT and float(value).is_integer():
            continue
        checked += 1
        if not _matches(abs(value), sources):
            unverified.append(raw)
    return {"ok": not unverified, "numbers_checked": checked, "unverified": unverified}


def for_model(result: dict) -> dict:
    """The part of a tool result the model sees and may quote.

    Chart series stay with the app: dozens of weekly points are no use to the
    model, and counting them as sources would make almost any number "found".
    """
    if isinstance(result, dict) and ("series" in result or "counted" in result):
        # "counted" (the payments behind a filtered total) is for the app's card as well: the
        # model answers from the total, and single payments must not make stray numbers "found".
        return {k: v for k, v in result.items() if k not in ("series", "counted")}
    return result


def compact(result: dict, limit: int = 7000) -> str:
    """Tool result as compact JSON for the model, cut down if it is very long."""
    result = for_model(result)
    text = json.dumps(result, ensure_ascii=False, separators=(",", ":"), default=str)
    if len(text) <= limit:
        return text
    trimmed = dict(result)
    for key in ("timeline", "rows", "transactions", "months", "breakdown"):
        if isinstance(trimmed.get(key), list) and len(trimmed[key]) > 12:
            trimmed[key] = trimmed[key][:12]
            trimmed[f"{key}_note"] = "list shortened to the first 12 entries"
    text = json.dumps(trimmed, ensure_ascii=False, separators=(",", ":"), default=str)
    return text[:limit]
