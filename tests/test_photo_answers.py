"""A photo answer always opens with what was read, in the language of the question."""

import json

import pytest

from app import agent, config

NBSP = " "
PHOTO = "data:image/jpeg;base64,AAAA"
READ = {"amount": 349, "what": "Nordwave Q7 Wireless", "category": "Home & Tech"}


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


def _answer(*args, **kwargs) -> dict:
    return next(e for e in reversed(list(agent.run(*args, **kwargs))) if e["type"] == "answer")


def test_the_line_is_there_when_the_model_leaves_it_out(model):
    model(_call(READ), _says("Ei juuri nyt. Palkkapäivää ennen tilisi saldo ei riitä tähän, joten kannattaa odottaa."))
    text = _answer("CUST00086", "Onko minulla varaa tähän?", [], image=PHOTO)["text"]
    assert text.startswith(f"Luin kuvasta: Nordwave Q7 Wireless, 349,00{NBSP}€.\n\nEi juuri nyt.")


def test_the_model_s_own_line_is_not_doubled(model):
    model(_call(READ), _says("I read: wireless headphones, 349,00 €.\n\nNot right now. Your balance would go below zero before payday."))
    text = _answer("CUST00086", "Can I afford this?", [], image=PHOTO)["text"]
    assert text.startswith("I read: Nordwave Q7 Wireless, €349.00.\n\nNot right now.")
    assert text.count("I read:") == 1 and "wireless headphones" not in text


def test_a_finnish_answer_to_an_english_question_is_asked_for_again_once(model):
    seen = model(
        _call(READ),
        _says("Ei juuri nyt. Palkkapäivää ennen tilisi saldo ei riitä tähän, joten kannattaa odottaa."),
        _says("Not right now. Your balance would go below zero before your next payday, so it is better to wait."),
    )
    answer = _answer("CUST00086", "Can I afford this?", [], image=PHOTO)
    assert len(seen) == 3 and "in English" in seen[2][-1]["content"]
    assert answer["text"].startswith("I read: Nordwave Q7 Wireless, €349.00.\n\nNot right now.")


def test_a_finnish_verdict_in_an_english_answer_is_put_right(model):
    seen = model(_call(READ), _says("Ei juuri nyt. Your balance would go below zero before your next payday, so it is better to wait."))
    text = _answer("CUST00086", "Can I afford this?", [], image=PHOTO)["text"]
    assert len(seen) == 2  # the answer is in English already: nothing is asked again
    assert text.startswith("I read: Nordwave Q7 Wireless, €349.00.\n\nNot right now. Your balance")


def test_a_photo_answer_without_a_lookup_is_asked_for_one_once(model):
    seen = model(
        _says("Ei juuri nyt. Kuulokkeet eivät mahdu tämän palkkakauden arjen budjettiin."),
        _call(READ),
        _says("Ei juuri nyt. Palkkapäivää ennen tilisi saldo ei riitä tähän, joten kannattaa odottaa."),
    )
    answer = _answer("CUST00086", "Onko minulla varaa tähän?", [], image=PHOTO)
    assert len(seen) == 3 and "check_affordability" in seen[1][-1]["content"]
    assert [t["name"] for t in answer["tools_used"]] == ["check_affordability"]
    assert answer["text"].startswith(f"Luin kuvasta: Nordwave Q7 Wireless, 349,00{NBSP}€.\n\nEi juuri nyt.")


def test_a_photo_with_no_price_to_read_is_asked_only_once(model):
    cannot = "En saa kuvasta hintaa selville. Paljonko se maksaa?"
    seen = model(_says(cannot), _says(cannot))
    text = _answer("CUST00086", "Onko minulla varaa tähän?", [], image=PHOTO)["text"]
    assert len(seen) == 2 and text == cannot


def test_a_question_without_a_photo_gets_no_such_line(model):
    model(_call({"amount": 349, "what": "headphones"}), _says("Not right now. Your balance would go below zero before your next payday."))
    text = _answer("CUST00086", "Can I afford headphones for 349 euros?", [])["text"]
    assert text.startswith("Not right now.") and "I read" not in text
