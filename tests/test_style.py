"""Amounts are written the way the answer's language does, and their values never change."""

import pytest

from app import grounding, style

NBSP = " "


def test_language_of_an_answer():
    assert style.answer_language("Yes. Your balance covers it and leaves you enough until payday.") == "en"
    assert style.answer_language("Kyllä. Saldo riittää ja tilillesi jää rahaa ennen seuraavaa palkkapäivää.") == "fi"
    assert style.answer_language("Ja, ditt saldo täcker det och du har pengar kvar till lönedagen.") == "sv"
    assert style.answer_language("Käytit pikaruokaan viimeisen kolmen kuukauden aikana €88.90.") == "fi"
    assert style.answer_language("Paljonko käytin pikaruokaan viimeisen kolmen kuukauden aikana?") == "fi"
    assert style.answer_language("Hur mycket har jag lagt på kläder de senaste tre månaderna?") == "sv"
    assert style.money("Käytit pikaruokaan viimeisen kolmen kuukauden aikana €88.90.").endswith(f"88,90{NBSP}€.")
    assert style.answer_language("349", fallback="fi") == "fi"
    assert style.answer_language("") == "en"


def test_english_answer_gets_english_amounts():
    said = (
        "I read: Nordwave Q7 Wireless, 349,00 €. Your balance covers it, leaving 152,19 € until payday on "
        "15 October, and 4 165,48 € is safe. You set aside about EUR 89 a month. It is €349,00 in all."
    )
    got = style.money(said)
    assert "€349.00." in got and "leaving €152.19 until" in got and "€4,165.48 is safe" in got
    assert "about €89 a month" in got and "It is €349.00 in all" in got
    assert "15 October" in got


def test_finnish_and_swedish_answers_get_their_own_style():
    fi = style.money("Kyllä. Saldo riittää ja tilillesi jää €19,062.42 ennen palkkapäivää. Ostos on EUR 349.")
    assert f"jää 19{NBSP}062,42{NBSP}€ ennen" in fi and f"on 349{NBSP}€." in fi
    sv = style.money("Ja, du har €152 kvar till lönedagen och brukar lägga 1,234.56 € på det.")
    assert f"har 152{NBSP}€ kvar" in sv and f"lägga 1{NBSP}234,56{NBSP}€ på" in sv


def test_the_euro_sign_of_one_amount_is_not_the_start_of_the_next_number():
    fi = style.money("Tilillesi jää 152 € 14 päivän ajaksi, ja se on vähemmän kuin tavallisesti.")
    assert f"jää 152{NBSP}€ 14 päivän" in fi
    en = style.money("That leaves €152 for the 14 days until payday, and you have 3 payments of 20 € each.")
    assert "leaves €152 for the 14 days" in en and "3 payments of €20 each" in en


def test_other_numbers_are_left_alone():
    said = "You made 12 purchases on 15 October, 10% more than usual, and a 120 euro jacket fits."
    assert style.money(said) == said
    assert style.money("") == "" and style.money(None) is None


@pytest.mark.parametrize(
    "said",
    [
        "I read: boots, 349,00 €. It leaves 1 152,19 € until payday and you usually spend €196.42 in that time.",
        "Luin kuvasta: kengät, €89.90. Tilillesi jää EUR 1,402.38 ja turvallista käyttää on 15,11 € tällä viikolla.",
        "Jag läste på bilden: skor, 89,90 €. Du har €1,402.38 kvar och det är 12 345 € mer än förra året.",
    ],
)
def test_values_survive_the_rewrite(said):
    before = sorted(value for _, value in grounding.numbers_in_text(said))
    after = sorted(value for _, value in grounding.numbers_in_text(style.money(said)))
    assert before == after
