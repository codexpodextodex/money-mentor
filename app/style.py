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
