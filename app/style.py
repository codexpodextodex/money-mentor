"""Write money the way the answer's language does, whatever the model wrote.

The model is told how to write amounts, but a Finnish price tag in a photo or
an "EUR 152" in a tool result can pull it the other way. This pass runs on the
finished answer, after the number check, and only changes how an amount is
written, never its value:

    English              €1,234.56
    Finnish and Swedish  1 234,56 €
"""

from __future__ import annotations

import re

_SPACES = "   "
_NBSP = " "

_WHOLE = rf"\d{{1,3}}(?:[{_SPACES},]\d{{3}})+|\d+"
# One pattern, tried left to right, so the € that ends "152 €" is never read as the start of the
# next number ("152 € 14 days").
#   symbol last:   1 234,56 €   349,00 €   152 €   349.00 €   1,234.56 €
#   symbol first:  €1,234.56    €349,00    EUR 152    € 1 234,56
_MONEY = re.compile(
    rf"(?<![\d.,])(?P<lw>{_WHOLE})(?:[.,](?P<lc>\d{{2}}))?[{_SPACES}]?€"
    rf"|(?:€|\bEUR)[{_SPACES}]?(?P<fw>{_WHOLE})(?:[.,](?P<fc>\d{{2}}))?(?!\d)"
)

_WORDS = {
    "fi": {
        "ja", "ei", "se", "että", "sinun", "sinulla", "jää", "tällä", "viikolla", "olet", "voit", "kun", "mutta",
        "tai", "ennen", "noin", "kyllä", "jos", "tämä", "sen", "tilisi", "saldo", "palkkapäivä", "palkkapäivää",
        "seuraava", "askel", "luin", "kuvasta", "ostos", "menot", "arjen", "euroa", "kuukaudessa", "vuodessa",
        "käytit", "käytin", "käyttänyt", "paljonko", "olen", "minulla", "onko", "varaa", "tähän", "mihin", "mitä",
        "ostin", "viime", "kuussa", "viimeisen", "kuukauden", "aikana", "kolmen", "yhteensä", "eli", "myös", "vain",
    },
    "sv": {
        "och", "är", "det", "du", "din", "ditt", "dina", "som", "inte", "för", "på", "har", "till", "den", "här",
        "veckan", "kan", "med", "av", "att", "men", "om", "nästa", "steg", "lönedagen", "kvar", "från", "eller",
        "hur", "mycket", "jag", "lagt", "lade", "senaste", "månaderna", "månaden", "råd", "vad", "köpte", "förra",
    },
    "en": {
        "the", "and", "is", "you", "your", "it", "of", "to", "this", "that", "for", "with", "are", "have",
        "before", "until", "but", "if", "next", "step", "payday", "week", "balance", "would", "from",
    },
}


def answer_language(text: str, fallback: str = "en") -> str:
    """'en', 'fi' or 'sv', by counting common words. Short or unclear text gets the fallback."""
    words = re.findall(r"[a-zåäöé]+", (text or "").lower())
    scores = {lang: sum(1 for w in words if w in vocab) for lang, vocab in _WORDS.items()}
    best = max(scores, key=scores.get)
    ranked = sorted(scores.values(), reverse=True)
    if ranked[0] == 0 or ranked[0] == ranked[1]:
        return fallback
    return best


_READ = {"en": "I read:", "fi": "Luin kuvasta:", "sv": "Jag läste på bilden:"}
_READ_ANY = re.compile(r"^\s*(I read:|Luin kuvasta:|Jag läste på bilden:)")


def lead_in(text: str, lang: str) -> str:
    """A photo answer opens with "I read: ...". Keep that opening in the answer's own language.

    A Finnish price tag can pull the model into "Luin kuvasta:" in an English answer.
    """
    if not text or lang not in _READ:
        return text
    return _READ_ANY.sub(_READ[lang], text, count=1)


def clear_language(text: str) -> str:
    """'en', 'fi' or 'sv' only when the text is clearly in that language, otherwise ''."""
    words = re.findall(r"[a-zåäöé]+", (text or "").lower())
    scores = sorted(((sum(1 for w in words if w in vocab), lang) for lang, vocab in _WORDS.items()), reverse=True)
    (best, lang), (second, _) = scores[0], scores[1]
    return lang if best >= 3 and best >= 2 * second else ""


# The model's own "I read: <item>, <price>." opening: up to the price when the line goes on, else the whole line.
_AMOUNT = rf"(?:(?:€|\bEUR)[{_SPACES}]?\d[\d.,{_SPACES}]*|\d[\d.,{_SPACES}]*[{_SPACES}]?€)"
_READ_LABEL = r"^\s*(?:I read|Luin kuvasta|Jag läste på bilden)\s*:"
_READ_LINE = re.compile(rf"{_READ_LABEL}[^\n]*?{_AMOUNT}\.?\s*|{_READ_LABEL}[^\n]*\n*")


def without_read_line(text: str) -> str:
    """The answer without the model's own "I read: ..." opening, if it wrote one."""
    return _READ_LINE.sub("", text or "", count=1).lstrip()


def read_from_photo(text: str, lang: str, what: str | None, amount) -> str:
    """Open a photo answer with what was read from the photo, so the customer can correct it.

    The line is written here, from what the model passed to the tool, because the model leaves it
    out in about half of its Finnish and Swedish answers. Any opening the model wrote is replaced.
    """
    lang = lang if lang in _READ else "en"
    try:
        price = money(f"€{float(amount):,.2f}", lang)
    except (TypeError, ValueError):
        return lead_in(text, lang)
    name = " ".join(str(what or "").split()).strip(" .,;:")
    line = f"{_READ[lang]} {name}, {price}." if name else f"{_READ[lang]} {price}."
    body = without_read_line(text)
    return f"{line}\n\n{body}" if body else line


# The fixed phrases a "can I afford it" answer opens with (the coach's prompt gives the same ones).
_VERDICTS = (
    {"en": "Yes.", "fi": "Kyllä.", "sv": "Ja."},
    {"en": "It fits, but it is tight.", "fi": "Se sopii, mutta on tiukilla.", "sv": "Det går, men det är tight."},
    {
        "en": "Not from this pay period's everyday budget.",
        "fi": "Ei tämän palkkakauden arjen budjetista.",
        "sv": "Inte från den här löneperiodens vardagsbudget.",
    },
    {"en": "Not right now.", "fi": "Ei juuri nyt.", "sv": "Inte just nu."},
)


def verdict(text: str, lang: str) -> str:
    """Keep the opening verdict in the answer's language ("Ei juuri nyt." in an English answer becomes "Not right now.")."""
    if not text or lang not in _READ:
        return text
    for phrases in _VERDICTS:
        for other, phrase in phrases.items():
            if other != lang and text.startswith(phrase):
                return phrases[lang] + text[len(phrase) :]
    return text


_FITS = ("yes", "tight", "not_from_this_budget", "no")  # the order of _VERDICTS


def verdict_for(text: str, lang: str, fits: str | None) -> str:
    """Open a "can I afford it" answer with the verdict the tool gave.

    The model sometimes opens with another of the fixed phrases ("Not right now." where the tool
    says "not from this budget"), or with the right one in the wrong language. Only an answer
    that opens with one of the fixed phrases is touched: the phrase is swapped, nothing else.
    """
    if not text or lang not in _READ or fits not in _FITS:
        return text
    right = _VERDICTS[_FITS.index(fits)][lang]
    for phrases in _VERDICTS:
        for phrase in phrases.values():
            if text.startswith(phrase):
                return right + text[len(phrase) :]
    return text


def _write(whole: str, cents: str | None, lang: str) -> str:
    digits = re.sub(r"\D", "", whole)
    if lang == "en":
        return f"€{int(digits):,}" + (f".{cents}" if cents else "")
    grouped = f"{int(digits):,}".replace(",", _NBSP)
    return grouped + (f",{cents}" if cents else "") + f"{_NBSP}€"


def money(text: str, lang: str | None = None) -> str:
    """Rewrite every euro amount in ``text`` in the style of ``lang`` (detected when not given)."""
    if not text or ("€" not in text and "EUR" not in text):
        return text
    lang = lang if lang in _WORDS else answer_language(text)

    def swap(match: re.Match) -> str:
        if match.group("lw") is not None:
            return _write(match.group("lw"), match.group("lc"), lang)
        return _write(match.group("fw"), match.group("fc"), lang)

    return _MONEY.sub(swap, text)
