"""A purchase that does not fit now comes back with when it could fit."""

import math

import pytest

from app import engine, offline, plan, replay, tools


def _just_over_the_budget(cid: str) -> float:
    """An everyday price a little above what is safe to spend until payday."""
    return engine.safe_to_spend(cid)["safe_to_spend_until_payday"] + 60


def test_a_purchase_that_fits_says_nothing_about_when():
    got = plan.can_afford("CUST00874", 120, "a jacket", "Lifestyle")
    assert got["fits"] == "yes" and "when" not in got


def test_room_in_the_next_pay_period_means_from_payday():
    cid = "CUST00001"
    price = _just_over_the_budget(cid)
    got = plan.can_afford(cid, price, "a jacket", "Lifestyle")
    nxt = plan.payday_plan(cid)
    budget = next(row["amount"] for row in nxt["split"] if row["key"] == "everyday")
    when = got["when"]
    assert got["fits"] == "not_from_this_budget" and when["route"] == "next_pay_period"
    assert when["earliest"] == nxt["payday"]["date"]
    period = when["next_pay_period"]
    assert period["has_room_for_it"] and period["everyday_budget"] == budget >= price
    assert period["left_for_everything_else"] == pytest.approx(budget - price, abs=0.01)
    assert period["left_for_everything_else_a_week"] == pytest.approx((budget - price) / nxt["pay_period"]["days"] * 7, abs=0.01)
    assert "one_habit" not in when


@pytest.mark.parametrize("price, category", [(120, "Lifestyle"), (349, "Home & Tech")])
def test_no_room_in_the_next_salary_names_the_habit_that_mattered_most(price, category):
    cid = "CUST00086"  # the default demo customer: the next salary has nothing for everyday spending
    got = plan.can_afford(cid, price, "x", category)
    top = replay.replay(cid)["levers"][0]
    when = got["when"]
    assert got["fits"] in ("no", "not_from_this_budget") and when["route"] == "one_habit"
    assert when["next_pay_period"]["has_room_for_it"] is False and when["next_pay_period"]["why_not"]
    habit = when["one_habit"]
    assert habit["lever"] == top["lever"] and habit["habit"] == top["title"]
    assert habit["would_have_kept_a_month"] == pytest.approx(top["kept_per_month"], abs=0.01)
    assert habit["months_for_this_price"] == math.ceil(price / top["kept_per_month"])
    assert "earliest" not in when


def test_a_balance_heading_below_zero_never_gets_a_payday_promise():
    cid = "CUST00086"
    assert plan.outlook(cid)["status"] == "short"
    assert plan.when_it_fits(cid, 1)["route"] != "next_pay_period"


def test_the_model_s_tool_and_the_fallback_both_carry_it():
    got = tools.call("CUST00086", "check_affordability", {"amount": 120, "what": "a jacket", "category": "Lifestyle"})
    assert got["when"]["one_habit"]["months_for_this_price"] == 2
    text = offline.describe("check_affordability", got)
    assert text.startswith("Not from this pay period's everyday budget.") and "about 2 months" in text and "not a promise" in text


def test_every_route_is_one_of_the_three():
    for cid in ("CUST00001", "CUST00002", "CUST00008", "CUST00226", "CUST00874"):
        when = plan.can_afford(cid, _just_over_the_budget(cid), "a jacket", "Lifestyle").get("when")
        assert when and when["route"] in ("next_pay_period", "one_habit", None)
        assert (when["route"] == "next_pay_period") == ("earliest" in when)


# ----------------------------------------------------- the model's side of it ---

import json  # noqa: E402

from app import agent, config  # noqa: E402


def _call(arguments: dict) -> dict:
    call = {"id": "c1", "type": "function", "function": {"name": "check_affordability", "arguments": json.dumps(arguments)}}
    return {"choices": [{"message": {"content": "", "tool_calls": [call]}}]}


def _says(text: str) -> dict:
    return {"choices": [{"message": {"content": text}}]}


@pytest.fixture
def model(monkeypatch):
    """A scripted model: each request gets the next reply, and the requests are kept."""
    seen: list[list[dict]] = []

    def script(*replies):
        queue = list(replies)

        def post(messages, use_tools=True):
            seen.append([dict(m) for m in messages])
            return queue.pop(0)

        monkeypatch.setattr(agent, "_post_chat", post)
        monkeypatch.setattr(config, "llm_configured", lambda: True)
        return seen

    return script


def test_the_model_is_given_when_with_its_summary_first(model):
    seen = model(_call({"amount": 120, "what": "takki", "category": "Lifestyle"}), _says("Ei tämän palkkakauden arjen budjetista."))
    list(agent.run("CUST00086", "Onko minulla varaa 120 euron takkiin?", []))
    given = json.loads(seen[1][-1]["content"])
    assert list(given["when"])[:2] == ["route", "in_short"] and "about 2 months" in given["when"]["in_short"]


def test_a_follow_up_answered_from_memory_is_sent_back_for_a_lookup(model):
    from_memory = "Noin kaksi kuukautta. Säästäisit 70,99 € kuukaudessa, ja 120,00 € kertyisi noin kahdessa kuukaudessa."
    seen = model(_says(from_memory), _call({"amount": 120, "what": "takki", "category": "Lifestyle"}), _says(from_memory))
    history = [
        {"role": "user", "content": "Onko minulla varaa 120 euron takkiin?"},
        {"role": "assistant", "content": "Ei tämän palkkakauden arjen budjetista."},
    ]
    events = list(agent.run("CUST00086", "Kuinka monta kuukautta minun pitää odottaa?", history))
    answer = next(e for e in reversed(events) if e["type"] == "answer")
    assert len(seen) == 3 and "without looking anything up" in seen[1][-1]["content"]
    assert [t["name"] for t in answer["tools_used"]] == ["check_affordability"]
    assert answer["grounding"]["ok"] and "70,99" in answer["text"]


def test_a_follow_up_that_needs_no_lookup_costs_one_more_round_and_keeps_its_answer(model):
    thanks = "Ole hyvä! Kysy lisää, jos jokin jäi mietityttämään."
    seen = model(_says(thanks), _says(thanks))
    history = [{"role": "user", "content": "Onko minulla varaa 120 euron takkiin?"}, {"role": "assistant", "content": "Ei tämän palkkakauden arjen budjetista."}]
    events = list(agent.run("CUST00086", "Kiitos!", history))
    answer = next(e for e in reversed(events) if e["type"] == "answer")
    assert len(seen) == 2 and answer["text"] == thanks and answer["tools_used"] == []


def test_a_first_question_without_a_lookup_is_not_sent_back(model):
    joke = "En ole paras vitsin kertoja, mutta autan mielelläni raha-asioissa."
    seen = model(_says(joke))
    events = list(agent.run("CUST00086", "Kerro vitsi", []))
    assert len(seen) == 1 and next(e for e in reversed(events) if e["type"] == "answer")["text"] == joke


# ------------------------------------------- what the app decides, not the model ---

from app import style  # noqa: E402


def test_the_opening_verdict_follows_the_tool():
    assert style.verdict_for("Ei juuri nyt. Syy.", "fi", "not_from_this_budget") == "Ei tämän palkkakauden arjen budjetista. Syy."
    assert style.verdict_for("Not right now. Why.", "en", "no") == "Not right now. Why."
    assert style.verdict_for("Ei juuri nyt. Why.", "en", "no") == "Not right now. Why."
    assert style.verdict_for("Inte just nu. Varför.", "sv", "not_from_this_budget") == "Inte från den här löneperiodens vardagsbudget. Varför."
    assert style.verdict_for("Noin kaksi kuukautta.", "fi", "no") == "Noin kaksi kuukautta."  # no verdict phrase: untouched


def test_a_result_with_one_reading_carries_no_need_or_treat_note():
    got = plan.can_afford("CUST00086", 349, "headphones", "Home & Tech")
    assert got["fits"] == "no" and "if_it_is_a_treat" not in got and "basket_depends_on" not in got["item"]
    both = plan.can_afford("CUST00874", 349, "headphones", "Home & Tech")
    assert "if_it_is_a_treat" in both and "basket_depends_on" in both["item"]


def test_the_summary_comes_in_three_languages_for_the_route_that_applies():
    habit = plan.when_it_fits("CUST00086", 120)
    assert habit["in_short_fi"] == "Ei seuraavasta palkastakaan. Yhtä tapaa muuttamalla noin 2 kuukaudessa."
    assert habit["in_short_sv"] == "Inte från nästa lön heller. Med en ändrad vana på ungefär 2 månader."
    room = plan.when_it_fits("CUST00001", _just_over_the_budget("CUST00001"))
    assert room["in_short_fi"].startswith("Seuraavasta palkkapäivästä alkaen (15.10.)") and "utrymme" in room["in_short_sv"]


def test_an_answer_that_contradicts_when_is_asked_for_again_once(model):
    wrong = "Ei tämän palkkakauden arjen budjetista. Seuraavasta palkkapäivästä alkaen: sen palkkakauden arjen budjetissa on tilaa."
    right = "Ei juuri nyt. Syy. Ei seuraavasta palkastakaan. Yhtä tapaa muuttamalla noin 2 kuukaudessa."
    seen = model(_call({"amount": 120, "what": "takki", "category": "Lifestyle"}), _says(wrong), _says(right))
    events = list(agent.run("CUST00086", "Onko minulla varaa 120 euron takkiin?", []))
    answer = next(e for e in reversed(events) if e["type"] == "answer")
    assert len(seen) == 3 and 'route "one_habit"' in seen[2][-1]["content"]
    # The model opened with the wrong verdict phrase; the app puts the tool's own verdict there.
    assert answer["text"].startswith("Ei tämän palkkakauden arjen budjetista. Syy. Ei seuraavasta palkastakaan.")
