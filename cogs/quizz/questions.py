"""Question generation. Answers are English-first; French names are accepted as aliases."""

import random

from cogs.quizz.countries import (
    CAPITAL_ALIASES,
    COUNTRIES,
    COUNTRY_ALIASES,
)


# The "en" field matches geopandas naming (used for map lookups). A few of
# those are abbreviations that read poorly as a shown answer, so override them.
_DISPLAY_OVERRIDE = {
    "S. Korea": "South Korea",
    "N. Korea": "North Korea",
    "Dem. Rep. Congo": "Democratic Republic of the Congo",
    "Bosnia and Herz.": "Bosnia and Herzegovina",
    "Macedonia": "North Macedonia",
}


def get_pool(difficulty: str) -> list[dict]:
    if difficulty == "all":
        return COUNTRIES.copy()
    pool = [c for c in COUNTRIES if c["difficulty"] == difficulty]
    return pool if len(pool) >= 8 else COUNTRIES.copy()


def _display_en(country: dict) -> str:
    """Nice English name shown as the answer."""
    return _DISPLAY_OVERRIDE.get(country["en"], country["en"])


def _capital_en(capital_fr: str) -> str:
    """English name of a capital (falls back to the stored name when identical)."""
    return CAPITAL_ALIASES.get(capital_fr, capital_fr)


def _country_aliases(country: dict) -> list[str]:
    """Accepted alternative spellings (geopandas name + French name + variants)."""
    answer = _display_en(country)
    aliases = [country["en"], country["fr"]]
    aliases += COUNTRY_ALIASES.get(country["fr"], [])
    return [a for a in dict.fromkeys(aliases) if a and a != answer]


def _all_capitals_fr(country: dict) -> list[str]:
    """Every accepted capital (French spelling); some countries have several."""
    return [country["capital_fr"], *country.get("extra_capitals_fr", [])]


def _all_capitals_en(country: dict) -> list[str]:
    """Every accepted capital (English spelling)."""
    return [_capital_en(c) for c in _all_capitals_fr(country)]


def _capital_aliases(country: dict) -> list[str]:
    """Accepted spellings for the capital(s): English + French variants, minus the primary answer."""
    answer = _capital_en(country["capital_fr"])
    aliases: list[str] = []
    for capital_fr in _all_capitals_fr(country):
        en = _capital_en(capital_fr)
        aliases.append(en)
        if capital_fr != en:
            aliases.append(capital_fr)
    return [a for a in dict.fromkeys(aliases) if a and a != answer]


def make_flag_question(country: dict) -> dict:
    return {
        "type": "flag",
        "text": "Which country does this flag belong to?",
        "answer": _display_en(country),
        "aliases": _country_aliases(country),
        "iso2": country["iso2"],
        "country_en": country["en"],
    }


def make_capital_question(country: dict) -> dict:
    variant = random.choice(["country_to_capital", "capital_to_country"])

    if variant == "country_to_capital":
        return {
            "type": "capital",
            "text": f"What is the capital of **{_display_en(country)}**?",
            "answer": _capital_en(country["capital_fr"]),
            "display_answer": " / ".join(_all_capitals_en(country)),
            "aliases": _capital_aliases(country),
            "country_en": country["en"],
        }
    capital_en = _capital_en(random.choice(_all_capitals_fr(country)))
    return {
        "type": "capital",
        "text": f"**{capital_en}** is the capital of which country?",
        "answer": _display_en(country),
        "aliases": _country_aliases(country),
        "country_en": country["en"],
    }


def make_map_question(country: dict) -> dict:
    return {
        "type": "map",
        "text": "Which country is highlighted in **red**?",
        "answer": _display_en(country),
        "aliases": _country_aliases(country),
        "country_en": country["en"],
    }


def make_shape_question(country: dict) -> dict:
    return {
        "type": "shape",
        "text": "Which country has this **shape**?",
        "answer": _display_en(country),
        "aliases": _country_aliases(country),
        "country_en": country["en"],
    }


_MAKERS = {
    "flag": make_flag_question,
    "capital": make_capital_question,
    "map": make_map_question,
    "shape": make_shape_question,
}


def generate_questions(
    question_types: list[str],
    difficulty: str,
    num_questions: int,
) -> list[dict]:
    pool = get_pool(difficulty)
    available = pool.copy()
    random.shuffle(available)

    type_cycle = question_types * (num_questions // len(question_types) + 1)
    random.shuffle(type_cycle)

    questions: list[dict] = []
    for i in range(num_questions):
        if not available:
            break
        country = available.pop(0)
        q_type = type_cycle[i % len(type_cycle)]
        questions.append(_MAKERS.get(q_type, make_flag_question)(country))

    return questions
