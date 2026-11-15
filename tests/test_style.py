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


def test_a_photo_answer_opens_in_its_own_language():
    english = "Luin kuvasta: Nordwave Q7 Wireless, €349.00.\n\nNot right now. Your balance covers €179.27 before payday."
    lang = style.answer_language(style._READ_ANY.sub("", english))
    assert lang == "en" and style.lead_in(english, lang).startswith("I read: Nordwave Q7 Wireless")
    finnish = "I read: kengät, 89,90 €.\n\nKyllä. Saldo riittää ja tilillesi jää rahaa ennen palkkapäivää."
    assert style.lead_in(finnish, "fi").startswith("Luin kuvasta: kengät")
    assert style.lead_in("Yes. It fits.", "en") == "Yes. It fits."


def test_the_app_writes_what_was_read_from_the_photo():
    # the model left the line out, as it often does in Finnish
    fi = style.read_from_photo("Ei juuri nyt.\n\nKuulokkeet maksavat 349,00 €.", "fi", "Nordwave Q7 Wireless", 349)
    assert fi == f"Luin kuvasta: Nordwave Q7 Wireless, 349,00{NBSP}€.\n\nEi juuri nyt.\n\nKuulokkeet maksavat 349,00 €."
    sv = style.read_from_photo("Ja. Ditt saldo räcker.", "sv", " Nordwave Q7  Wireless. ", 1349.5)
    assert sv.startswith(f"Jag läste på bilden: Nordwave Q7 Wireless, 1{NBSP}349,50{NBSP}€.\n\nJa.")
    # the model wrote its own line, in the wrong language and with its own wording: it is replaced, not doubled
    en = style.read_from_photo("Luin kuvasta: langattomat kuulokkeet, 349,00 €.\n\nNot right now. Wait until payday.", "en", "Nordwave Q7 Wireless", 349.0)
    assert en == "I read: Nordwave Q7 Wireless, €349.00.\n\nNot right now. Wait until payday."
    # the model's line and the verdict on one line: only the line about the photo goes
    same_line = style.read_from_photo("I read: boots, €89.90. Yes. It leaves €40 this week.", "en", "boots", "89.9")
    assert same_line == "I read: boots, €89.90.\n\nYes. It leaves €40 this week."
    # no name: the price alone; no usable price: the answer is left as the model wrote it
    assert style.read_from_photo("Yes.", "en", None, 12) == "I read: €12.00.\n\nYes."
    assert style.read_from_photo("Yes.", "en", "boots", "about fifty") == "Yes."


def test_the_model_s_own_line_about_the_photo_is_found():
    assert style.without_read_line("I read: boots, €89.90.\n\nYes.") == "Yes."
    assert style.without_read_line("Luin kuvasta: kengät, 1 234,56 €. Kyllä.") == "Kyllä."
    assert style.without_read_line("Jag läste på bilden: skor\n\nJa.") == "Ja."
    assert style.without_read_line("Yes. I read it twice.") == "Yes. I read it twice."


def test_the_verdict_is_said_in_the_answer_s_language():
    assert style.verdict("Ei juuri nyt. After the bills your balance covers €179.27.", "en").startswith("Not right now. After the bills")
    assert style.verdict("Yes. Saldo riittää.", "fi") == "Kyllä. Saldo riittää."
    assert style.verdict("It fits, but it is tight. Det lämnar 12,00 €.", "sv").startswith("Det går, men det är tight. Det lämnar")
    assert style.verdict("Not right now. Wait.", "en") == "Not right now. Wait."
    assert style.verdict("Jatka samaan malliin.", "en") == "Jatka samaan malliin."


def test_a_language_is_only_called_clear_when_it_is():
    assert style.clear_language("Ei juuri nyt. Palkkapäivää ennen tilisi saldo ei riitä tähän, mutta voit odottaa.") == "fi"
    assert style.clear_language("Not right now. Your balance would go below zero before payday, but you have options.") == "en"
    assert style.clear_language("Inte just nu. Du har inte råd med det här före lönedagen.") == "sv"
    assert style.clear_language("Nordwave Q7 Wireless, 349,00 €") == ""
    assert style.clear_language("") == ""


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
