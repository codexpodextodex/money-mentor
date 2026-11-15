"""A payment draft from a bill the customer photographed.

The model reads the bill. Nothing it reads is trusted until it has been checked here: an IBAN
and a Finnish reference number both carry check digits, so a misread digit is caught by
arithmetic and not by hoping. The result is a draft for the customer to look over. Nothing is
ever paid by this code, and the result says so.
"""

from __future__ import annotations

import datetime as dt
import re

from . import baskets, db, engine
from .engine import EngineError, _r

NOTHING_IS_PAID = (
    "This is a draft for the customer to check. Nothing is paid until the customer confirms it in the app "
    "with their own approval. In this demo nothing is paid at all."
)
IBAN_LENGTHS = {"FI": 18, "SE": 24, "EE": 20, "DE": 22, "NO": 15, "DK": 18, "NL": 18, "FR": 27, "ES": 24, "GB": 22, "LT": 20, "LV": 21}


def _grouped(text: str, size: int = 4, from_right: bool = False) -> str:
    if from_right:
        text = text[::-1]
    out = " ".join(text[i : i + size] for i in range(0, len(text), size))
    return out[::-1] if from_right else out


def check_iban(text: str | None) -> dict:
    """Whether an account number is a well-formed IBAN whose check number is right (ISO 13616, mod 97)."""
    raw = re.sub(r"[\s.\-]", "", str(text or "")).upper()
    if not raw:
        return {"status": "missing"}
    out = {"as_read": raw}
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{10,30}", raw):
        return {**out, "status": "does_not_check_out", "why": "It does not have the shape of an IBAN."}
    country = raw[:2]
    if country in IBAN_LENGTHS and len(raw) != IBAN_LENGTHS[country]:
        return {
            **out,
            "status": "does_not_check_out",
            "why": f"An IBAN from {country} has {IBAN_LENGTHS[country]} characters, and this has {len(raw)}: a character is missing or extra.",
        }
    digits = "".join(str(int(ch, 36)) for ch in raw[4:] + raw[:4])
    if int(digits) % 97 != 1:
        return {**out, "status": "does_not_check_out", "why": "Its check number does not match the rest: a digit was probably misread."}
    return {"status": "checks_out", "iban": _grouped(raw)}


def check_reference(text: str | None) -> dict:
    """Whether a reference is a Finnish reference number (weights 7-3-1) or an RF creditor reference (ISO 11649)."""
    raw = re.sub(r"[\s.\-]", "", str(text or "")).upper()
    if not raw:
        return {"status": "missing"}
    out = {"as_read": raw}
    if raw.startswith("RF"):
        if not re.fullmatch(r"RF\d{2}[A-Z0-9]{1,21}", raw):
            return {**out, "status": "does_not_check_out", "why": "It does not have the shape of an RF reference."}
        digits = "".join(str(int(ch, 36)) for ch in raw[4:] + raw[:4])
        if int(digits) % 97 != 1:
            return {**out, "status": "does_not_check_out", "why": "Its check number does not match the rest: a character was probably misread."}
        return {"status": "checks_out", "reference": _grouped(raw)}
    if not raw.isdigit() or not 4 <= len(raw) <= 20:
        return {**out, "status": "does_not_check_out", "why": "A Finnish reference number is 4 to 20 digits."}
    total = sum(int(d) * (7, 3, 1)[i % 3] for i, d in enumerate(reversed(raw[:-1])))
    if (10 - total % 10) % 10 != int(raw[-1]):
        return {**out, "status": "does_not_check_out", "why": "Its last digit, the check digit, does not match the rest: a digit was probably misread."}
    return {"status": "checks_out", "reference": _grouped(raw, 5, from_right=True)}


_MONTHS = {
    name: number
    for number, names in enumerate(
        [
            "january jan tammikuu tammikuuta januari",
            "february feb helmikuu helmikuuta februari",
            "march mar maaliskuu maaliskuuta mars",
            "april apr huhtikuu huhtikuuta",
            "may toukokuu toukokuuta maj",
            "june jun kesäkuu kesäkuuta juni",
            "july jul heinäkuu heinäkuuta juli",
            "august aug elokuu elokuuta augusti",
            "september sep sept syyskuu syyskuuta",
            "october oct lokakuu lokakuuta oktober okt",
            "november nov marraskuu marraskuuta",
            "december dec joulukuu joulukuuta",
        ],
        start=1,
    )
    for name in names.split()
}


def _date(text: str | None) -> dt.date | None:
    """A date as a bill prints it. Numbers with dots or slashes are day first, as Finnish bills write them."""
    text = " ".join(str(text or "").split()).strip(" .,")
    if not text:
        return None
    found = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if found:
        year, month, day = (int(x) for x in found.groups())
    elif found := re.fullmatch(r"(\d{1,2})[./](\d{1,2})[./](\d{4}|\d{2})", text):
        day, month, year = (int(x) for x in found.groups())
        year += 2000 if year < 100 else 0
    elif found := re.fullmatch(r"(\d{1,2})\.?(?: of)? ([a-zåäö]+)\.?,? (\d{4})", text.lower()):
        day, month, year = int(found.group(1)), _MONTHS.get(found.group(2)), int(found.group(3))
    elif found := re.fullmatch(r"([a-zåäö]+)\.? (\d{1,2})(?:st|nd|rd|th)?,? (\d{4})", text.lower()):
        day, month, year = int(found.group(2)), _MONTHS.get(found.group(1)), int(found.group(3))
    else:
        raise EngineError("due_date must be the date exactly as the bill prints it, for example 10.12.2026 or 24 December 2026.")
    try:
        return dt.date(year, month or 0, day)
    except ValueError as exc:
        raise EngineError("due_date is not a real date. Pass it exactly as the bill prints it.") from exc


def _money(value) -> float | None:
    """An amount as a number, from a number or from the way a bill prints it ("1 234,56 €", "€1,234.56")."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace("\u00a0", " ").strip()
    if not re.fullmatch(r"(?:€|EUR)?\s*\d[\d\s.,]*\s*(?:€|EUR|eur|e|euroa|euro)?", text):
        return None
    digits = re.sub(r"[^\d.,]", "", text).strip(".,")
    last = max(digits.rfind(","), digits.rfind("."))
    if last >= 0 and len(digits) - last - 1 in (1, 2):
        digits = re.sub(r"[.,]", "", digits[:last]) + "." + digits[last + 1 :]
    else:
        digits = re.sub(r"[.,]", "", digits)
    try:
        return float(digits)
    except ValueError:
        return None


_AMOUNT = re.compile(r"(?<![\d.,])(\d{1,3}(?:[ \u00a0.,]\d{3})+[.,]\d{2}|\d+[.,]\d{2})(?![.,]?\d)")
_DATE = re.compile(
    r"\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[./]\d{1,2}[./](?:\d{4}|\d{2})\b|\d{1,2}\.? [A-Za-zåäöÅÄÖ]+,? \d{4}|[A-Za-z]+ \d{1,2}(?:st|nd|rd|th)?,? \d{4}"
)
_TOTAL_WORDS = (
    ("maksettava yhteensä", "maksettavaa yhteensä", "att betala", "summa att betala", "amount due", "total due", "amount to pay", "to pay", "maksettava"),
    ("yhteensä", "loppusumma", "totalt", "summa", "total"),
)
_DUE_WORDS = ("eräpäivä", "förfallodag", "förfallodatum", "due date", "payment due", "pay by", "due")
_MONEY_MARKS = ("€", "eur", "euro")


def read_text_of_bill(text: str | None) -> dict:
    """The total, the due date and the largest amount, found by rule in a bill's text.

    The text is the model's copy of the bill, line by line. Nothing is chosen by the model here:
    the total is the amount on the line that says "total to pay" (or right under it), the due date
    the date on the line that says "due date", and the largest amount is simply the largest.
    """
    lines = [" ".join(line.replace("\u00a0", " ").split()) for line in str(text or "").splitlines()]
    lines = [line.strip(" |*-") for line in lines if line.strip(" |*-")]
    lowered = [line.lower() for line in lines]

    def value_after(index: int, pattern: re.Pattern) -> str | None:
        # On the label's own line, else on the next line (a copy may break a row in two).
        for line in lines[index : index + 2]:
            found = pattern.findall(line)
            if found:
                return found[-1] if isinstance(found[-1], str) else found[-1][0]
        return None

    total = None
    for words in _TOTAL_WORDS:
        at = next((i for i, line in enumerate(lowered) if any(word in line for word in words)), None)
        if at is not None:
            total = value_after(at, _AMOUNT)
            if total:
                break
    due = None
    at = next((i for i, line in enumerate(lowered) if any(word in line for word in _DUE_WORDS)), None)
    if at is not None:
        due = value_after(at, _DATE)
    amounts = [m for line, low in zip(lines, lowered) if any(mark in low for mark in _MONEY_MARKS) for m in _AMOUNT.findall(line)]
    values = [(value, shown) for shown in amounts if (value := _money(shown)) is not None]
    largest = max(values)[1] if values else None
    return {"amount": total, "due_date": due, "largest_amount": largest}


def payment_draft(
    customer_id: str,
    amount: float,
    payee: str | None = None,
    iban: str | None = None,
    reference: str | None = None,
    due_date: str | None = None,
    bill_date: str | None = None,
    category: str | None = None,
    second_reading: dict | None = None,
) -> dict:
    """A payment prepared from a bill: the fields as read, checked, with what the balance says about it.

    second_reading is not the model's to pass: the app adds it. It is the total and the due date
    read from the photo a second time, on their own. Those two fields have no check digit, so
    the draft is ready only when both readings agree.
    """
    cid = engine.customer(customer_id)["customer_id"]
    amount = _money(amount)
    if amount is None:
        raise EngineError("amount must be a number of euros: the total to pay, for example 84.60.")
    if not 0 < amount <= 1_000_000:
        raise EngineError("amount must be a positive number of euros.")
    name = None
    if category:
        name = engine._match_category(category)
        if not name:
            raise EngineError(f"Unknown category '{category}'. Categories: {', '.join(baskets.SPEND_CATEGORIES)}.")
    today = db.today()
    due = _date(due_date)
    account = check_iban(iban)
    ref = check_reference(reference)

    problems = []
    if account["status"] == "missing":
        problems.append("No account number was read from the bill.")
    elif account["status"] != "checks_out":
        problems.append(f"The account number does not check out. {account['why']} Compare it with the bill, or take the photo again.")
    if ref["status"] == "does_not_check_out":
        problems.append(f"The reference number does not check out. {ref['why']} Compare it with the bill, or take the photo again.")

    read_twice = {"amount": "read_once", "due_date": "read_once" if due else "missing"}
    if isinstance(second_reading, dict):
        amount_again = _money(second_reading.get("amount"))
        largest = _money(second_reading.get("largest_amount"))
        if amount_again is None:
            # The second look was tried and gave nothing to compare with: one reading is not enough.
            read_twice["amount"] = "not_read_twice"
            problems.append("The amount could not be read a second time, so it has nothing to be compared with. Read the bill again.")
        elif abs(amount_again - amount) >= 0.005:
            read_twice["amount"] = "readings_differ"
            problems.append(
                f"Two readings of the amount disagree: {amount:.2f} and {amount_again:.2f}. Read the total to pay again: "
                "the figure next to the words for the total, not one line of the bill."
            )
        elif largest is not None and largest - amount >= 0.005:
            # Both readings can settle on the same line of the bill. A total is never the smaller figure.
            read_twice["amount"] = "smaller_than_another_amount"
            problems.append(
                f"The amount read as the total ({amount:.2f}) is smaller than another amount printed on the bill ({largest:.2f}), "
                "so a line of the bill was probably read instead of the total. Read the total to pay again."
            )
        else:
            read_twice["amount"] = "read_twice_same"
        try:
            due_again = _date(second_reading.get("due_date"))
        except EngineError:
            due_again = None
        if due_again and due:
            read_twice["due_date"] = "read_twice_same" if due_again == due else "readings_differ"
        elif due_again and not due:
            read_twice["due_date"] = "readings_differ"
        if read_twice["due_date"] == "readings_differ":
            problems.append(
                f"Two readings of the due date disagree: {due.isoformat() if due else 'none'} and {due_again.isoformat()}. "
                "Read the due date again and pass it exactly as the bill prints it."
            )

    # A bill carries two dates, and they get mixed up. The due date is the later one.
    try:
        issued = _date(bill_date)
    except EngineError:
        issued = None
    if due and issued and due <= issued:
        read_twice["due_date"] = "not_after_the_bill_date"
        problems.append(
            f"The due date read ({due.isoformat()}) is not after the bill's own date ({issued.isoformat()}), so the two were "
            "probably mixed up. Find the due date again: it is next to the words for it (Eräpäivä, Förfallodag, Due date)."
        )

    draft: dict = {
        "payee": " ".join(str(payee or "").split())[:80] or None,
        "account_number": account.get("iban") or account.get("as_read"),
        "reference": ref.get("reference") or ref.get("as_read"),
        "amount": _r(amount),
        "due_date": due.isoformat() if due else None,
    }
    if due:
        draft["due_in_days"] = (due - today).days
        draft["overdue"] = due < today

    safe = engine.safe_to_spend(cid)
    balance = float(safe["balance_check"]["balance_today"])
    next_payday = safe["pay_period"]["next_payday"]
    result = {
        "customer_id": cid,
        "draft": draft,
        "checks": {
            "account_number": account["status"],
            "reference": ref["status"],
            "amount": read_twice["amount"],
            "due_date": read_twice["due_date"],
            "how": (
                "The check digits inside the account number and the reference number were recalculated. "
                "The amount and the due date have no check digit, so they were read from the photo a second time and compared."
            ),
        },
        "ready_to_confirm": not problems,
        "problems": problems,
        "balance": {
            "today": _r(balance),
            "covers_it": balance >= amount,
            "left_on_the_account_after": _r(balance - amount),
            "next_payday": next_payday,
        },
        "nothing_is_paid": NOTHING_IS_PAID,
    }
    if due:
        result["balance"]["due_before_next_payday"] = due.isoformat() < next_payday
    if name:
        basket, reason = engine.basket_for_purchase(name, amount)
        result["basket"] = {"name": baskets.BASKETS[basket]["name"], "category": name, "why": reason}
        if name == "Utilities":
            usual = engine.bill_habits(cid, today).get("utilities_payment")
            if usual:
                # Utility bills are already in the pay period's budget at their six-month average.
                result["already_in_the_budget"] = {
                    "usual_utility_bills_a_month": _r(usual["a_month"]),
                    "why": "Utility bills are part of the regular essentials the budget sets aside before anything else.",
                }
    return result
