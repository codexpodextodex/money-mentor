"""A bill read from a photo becomes a draft only after its check digits have been recalculated."""

import json

import pytest

from app import agent, bills, config, engine, tools

IBAN = "FI87 9999 9900 0123 44"  # made up: bank code 99 belongs to no bank, the check number is right
REFERENCE = "20261 04577"
BILL = {"payee": "Demo Sähkö Oy", "iban": IBAN, "reference": REFERENCE, "amount": 84.6, "due_date": "2026-10-12", "category": "Utilities"}


def test_a_well_read_bill_is_ready_to_confirm_and_nothing_is_paid():
    got = bills.payment_draft("CUST00086", **BILL)
    assert got["ready_to_confirm"] and got["problems"] == []
    assert got["checks"]["account_number"] == got["checks"]["reference"] == "checks_out"
    assert got["draft"] == {
        "payee": "Demo Sähkö Oy",
        "account_number": "FI87 9999 9900 0123 44",
        "reference": "20261 04577",
        "amount": 84.6,
        "due_date": "2026-10-12",
        "due_in_days": 12,
        "overdue": False,
    }
    assert "nothing is paid" in got["nothing_is_paid"].lower()


def test_the_balance_part_is_the_customer_s_own():
    got = bills.payment_draft("CUST00086", **BILL)
    balance = engine.safe_to_spend("CUST00086")["balance_check"]["balance_today"]
    assert got["balance"]["today"] == balance and got["balance"]["covers_it"] is True
    assert got["balance"]["left_on_the_account_after"] == pytest.approx(balance - 84.6, abs=0.01)
    assert got["balance"]["due_before_next_payday"] is True
    assert got["basket"]["name"] == "Regular essentials" and got["already_in_the_budget"]["usual_utility_bills_a_month"] > 0
    assert bills.payment_draft("CUST00086", amount=5000, iban=IBAN)["balance"]["covers_it"] is False


@pytest.mark.parametrize(
    "misread",
    ["FI87 9999 9900 0123 45", "FI87 9999 9900 0132 44", "FI78 9999 9900 0123 44", "FI87 9999 9900 0123 4", "F187 9999 9900 0123 44"],
)
def test_a_misread_account_number_is_caught(misread):
    got = bills.payment_draft("CUST00086", **{**BILL, "iban": misread})
    assert got["checks"]["account_number"] == "does_not_check_out" and not got["ready_to_confirm"]
    assert "account number does not check out" in got["problems"][0]


@pytest.mark.parametrize("misread", ["20261 04578", "20261 40577", "2026 104577 1"])
def test_a_misread_reference_is_caught(misread):
    got = bills.payment_draft("CUST00086", **{**BILL, "reference": misread})
    assert got["checks"]["reference"] == "does_not_check_out" and not got["ready_to_confirm"]


def test_other_shapes_of_account_and_reference():
    assert bills.check_iban("fi8799999900012344")["status"] == "checks_out"
    assert bills.check_iban("GB82 WEST 1234 5698 7654 32")["status"] == "checks_out"  # the standard example IBAN
    assert bills.check_iban("")["status"] == "missing" and bills.check_iban("12345")["status"] == "does_not_check_out"
    assert bills.check_reference("RF18 5390 0754 7034")["status"] == "checks_out"  # the standard example RF reference
    assert bills.check_reference("RF18 5390 0754 7035")["status"] == "does_not_check_out"
    assert bills.check_reference(None)["status"] == "missing"
    no_reference = bills.payment_draft("CUST00086", amount=20, iban=IBAN)
    assert no_reference["ready_to_confirm"] and no_reference["checks"]["reference"] == "missing"
    assert not bills.payment_draft("CUST00086", amount=20)["ready_to_confirm"]


def test_bad_input_is_an_error_the_model_can_fix():
    assert "error" in tools.call("CUST00086", "prepare_payment", {"amount": 0, "iban": IBAN})
    assert "error" in tools.call("CUST00086", "prepare_payment", {"amount": 10, "iban": IBAN, "due_date": "soon"})
    assert tools.call("CUST00086", "prepare_payment", {"amount": 10, "iban": IBAN, "due_date": "12.10.2026"})["draft"]["due_date"] == "2026-10-12"


def test_a_date_is_read_the_way_the_bill_prints_it():
    # Day first: the model swapped these two when it converted the date itself.
    assert bills.payment_draft("CUST00086", amount=10, iban=IBAN, due_date="10.12.2026")["draft"]["due_date"] == "2026-12-10"
    assert bills.payment_draft("CUST00086", amount=10, iban=IBAN, due_date="24 December 2026")["draft"]["due_date"] == "2026-12-24"
    assert bills.payment_draft("CUST00086", amount=10, iban=IBAN, due_date="6. tammikuuta 2027")["draft"]["due_date"] == "2027-01-06"
    assert bills._money("1 234,56 €") == bills._money("€1,234.56") == 1234.56 and bills._money("431.amount>431.25") is None


def test_amount_and_due_date_must_agree_with_a_second_reading():
    same = bills.payment_draft("CUST00086", **BILL, second_reading={"amount": "84,60 €", "due_date": "12.10.2026"})
    assert same["ready_to_confirm"] and same["checks"]["amount"] == same["checks"]["due_date"] == "read_twice_same"
    line_item = bills.payment_draft("CUST00086", **{**BILL, "amount": 41.2}, second_reading={"amount": "84,60 €", "due_date": "12.10.2026"})
    assert not line_item["ready_to_confirm"] and line_item["checks"]["amount"] == "readings_differ"
    assert "41.20 and 84.60" in line_item["problems"][0]
    swapped = bills.payment_draft("CUST00086", **{**BILL, "due_date": "2026-12-10"}, second_reading={"amount": 84.6, "due_date": "12.10.2026"})
    assert not swapped["ready_to_confirm"] and swapped["checks"]["due_date"] == "readings_differ"
    once = bills.payment_draft("CUST00086", **BILL)
    assert once["ready_to_confirm"] and once["checks"]["amount"] == "read_once"


def test_a_due_date_that_is_not_after_the_bill_s_own_date_is_held_back():
    mixed_up = bills.payment_draft("CUST00086", **{**BILL, "due_date": "28.9.2026"}, bill_date="28.9.2026", second_reading={"amount": 84.6, "due_date": "28.9.2026"})
    assert not mixed_up["ready_to_confirm"] and mixed_up["checks"]["due_date"] == "not_after_the_bill_date"
    assert "mixed up" in mixed_up["problems"][-1]
    fine = bills.payment_draft("CUST00086", **BILL, bill_date="28.9.2026", second_reading={"amount": 84.6, "due_date": "12.10.2026"})
    assert fine["ready_to_confirm"] and fine["checks"]["due_date"] == "read_twice_same"
    assert bills.payment_draft("CUST00086", **BILL, bill_date="not a date")["ready_to_confirm"]


def test_a_total_is_never_smaller_than_another_amount_on_the_bill():
    # Both readings settled on the same line of the bill: the larger figure printed on it gives that away.
    line = bills.payment_draft("CUST00086", **{**BILL, "amount": 41.2}, second_reading={"amount": "41,20 €", "due_date": "12.10.2026", "largest_amount": "84,60 €"})
    assert not line["ready_to_confirm"] and line["checks"]["amount"] == "smaller_than_another_amount"
    total = bills.payment_draft("CUST00086", **BILL, second_reading={"amount": "84,60 €", "due_date": "12.10.2026", "largest_amount": "84,60 €"})
    assert total["ready_to_confirm"] and total["checks"]["amount"] == "read_twice_same"


def test_one_reading_is_not_enough_when_the_second_was_tried():
    failed = bills.payment_draft("CUST00086", **BILL, second_reading={})
    assert not failed["ready_to_confirm"] and failed["checks"]["amount"] == "not_read_twice"
    assert bills.payment_draft("CUST00086", **BILL)["ready_to_confirm"]  # typed in, no photo: nothing to read twice


def test_the_total_is_found_in_the_bill_s_text_by_its_label():
    got = bills.read_text_of_bill(COPY)
    assert got == {"amount": "84,60", "due_date": "12.10.2026", "largest_amount": "84,60"}
    # A total over a thousand, printed with a space, under three lines of the bill: the case the model got wrong.
    big = bills.read_text_of_bill("Perusmaksu 744,08 €\nKäyttömaksu 1 098,18 €\nPalvelumaksu 1 304,31 €\nEräpäivä\n20.10.2026\nMaksettava yhteensä\n3 146,57 €")
    assert bills._money(big["amount"]) == 3146.57 and big["due_date"] == "20.10.2026" and bills._money(big["largest_amount"]) == 3146.57
    english = bills.read_text_of_bill("Invoice date 28.9.2026\nUsage €1,098.18\nDue date 24 December 2026\nAmount due €3,146.57")
    assert bills._money(english["amount"]) == 3146.57 and english["due_date"] == "24 December 2026"
    swedish = bills.read_text_of_bill("Förfallodag 19.12.2026\nAtt betala 164,96 €\nMottagarens kontonummer (IBAN) FI69 9921 5241 7370 87")
    assert bills._money(swedish["amount"]) == 164.96 and swedish["due_date"] == "19.12.2026"
    assert bills.read_text_of_bill("nothing useful here") == {"amount": None, "due_date": None, "largest_amount": None}


def test_the_model_cannot_supply_the_second_reading_itself():
    assert "error" in tools.call("CUST00086", "prepare_payment", {**BILL, "second_reading": {"amount": 84.6}})
    assert tools.call("CUST00086", "prepare_payment", BILL, {"second_reading": {"amount": "84,60 €"}})["checks"]["amount"] == "read_twice_same"


def _tool_call(arguments: dict) -> dict:
    call = {"id": "c1", "type": "function", "function": {"name": "prepare_payment", "arguments": json.dumps(arguments)}}
    return {"choices": [{"message": {"content": "", "tool_calls": [call]}}]}


def _says(text: str) -> dict:
    return {"choices": [{"message": {"content": text}}]}


ANSWER = "Lasku on Demo Sähkö Oy:ltä: 84,60 €, eräpäivä 12.10. Tilinumero ja viite täsmäävät. Mitään ei makseta ennen kuin vahvistat."
COPY = """Demo Sähkö Oy LASKU
Laskun päivämäärä 28.9.2026
Sähköenergia 412 kWh 41,20 €
Sähkön siirto 31,90 €
MAKSUTIEDOT
Saaja Demo Sähkö Oy
Saajan tilinumero (IBAN) FI87 9999 9900 0123 44
Viitenumero 20261 04577
Eräpäivä 12.10.2026
Maksettava yhteensä 84,60 €"""
SECOND = _says(COPY)


def _run(monkeypatch, *replies):
    seen, queue = [], list(replies)

    def post(messages, use_tools=True):
        seen.append([dict(m) for m in messages])
        return queue.pop(0)

    monkeypatch.setattr(agent, "_post_chat", post)
    monkeypatch.setattr(config, "llm_configured", lambda: True)
    events = list(agent.run("CUST00086", "Maksa tämä lasku", [], image="data:image/jpeg;base64,AAAA"))
    return seen, events, next(e for e in reversed(events) if e["type"] == "answer")


def test_a_bill_photo_goes_through_the_tool_and_is_read_twice(monkeypatch):
    seen, events, answer = _run(monkeypatch, _tool_call({**BILL, "due_date": "12.10.2026"}), SECOND, _says(ANSWER))
    assert len(seen) == 3 and "Copy all the text" in seen[1][0]["content"][0]["text"]  # the second look is its own request
    result = next(e["result"] for e in events if e["type"] == "tool_result")
    assert result["ready_to_confirm"] and result["checks"]["amount"] == result["checks"]["due_date"] == "read_twice_same"
    assert [t["name"] for t in answer["tools_used"]] == ["prepare_payment"] and answer["grounding"]["ok"]
    assert answer["text"].startswith("Lasku on Demo Sähkö Oy:ltä")  # no "I read: ..." line: the card shows the fields


def test_a_failed_check_sends_the_model_back_to_the_photo_once(monkeypatch):
    misread = {**BILL, "iban": "FI87 9999 9900 0123 45", "due_date": "12.10.2026"}
    seen, events, answer = _run(monkeypatch, _tool_call(misread), SECOND, _tool_call({**BILL, "due_date": "12.10.2026"}), SECOND, _says(ANSWER))
    drafts = [e["result"] for e in events if e["type"] == "tool_result"]
    assert [d["ready_to_confirm"] for d in drafts] == [False, True]
    assert "The draft is not ready" in seen[2][-1]["content"] and "account number does not check out" in seen[2][-1]["content"]
    assert len(seen) == 5 and answer["grounding"]["ok"]


def test_a_draft_that_still_fails_is_not_read_a_third_time(monkeypatch):
    misread = {**BILL, "iban": "FI87 9999 9900 0123 45"}
    sorry = "Tilinumero ei läpäissyt tarkistusta. Vertaa sitä laskuun tai ota kuva uudelleen."
    seen, events, answer = _run(monkeypatch, _tool_call(misread), SECOND, _tool_call(misread), SECOND, _says(sorry))
    assert [e["result"]["ready_to_confirm"] for e in events if e["type"] == "tool_result"] == [False, False]
    assert len(seen) == 5 and answer["text"] == sorry
