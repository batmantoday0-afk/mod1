# mod1_modules/pokemon.py
# Normalization utilities for the command-generator app.
# Provides normalize_name(raw: str) -> str

import re
from typing import Optional

# Minimal fallback pokedex (keeps app usable if no pokedex.json present)
MINIMAL_POKEDEX = [
    {"name": "Bulbasaur", "gen": 1}, {"name": "Ivysaur", "gen": 1}, {"name": "Venusaur", "gen": 1},
    {"name": "Charmander", "gen": 1}, {"name": "Charmeleon", "gen": 1}, {"name": "Charizard", "gen": 1},
    {"name": "Squirtle", "gen": 1}, {"name": "Wartortle", "gen": 1}, {"name": "Blastoise", "gen": 1},
    {"name": "Pikachu", "gen": 1}, {"name": "Raichu", "gen": 1},
    {"name": "Vulpix", "gen": 1}, {"name": "Vulpix (Alolan)", "gen": 7},
    {"name": "Meowth", "gen": 1}, {"name": "Meowth (Galarian)", "gen": 8},
]

# Map common variant tokens to canonical prefix used in outputs (lowercase)
_VARIANT_MAP = {
    "alolan": "alolan",
    "alola": "alolan",
    "galarian": "galarian",
    "galar": "galarian",
    "hisuian": "hisuian",
    "hisuia": "hisuian",
    "paldean": "paldean",
    "paldea": "paldean",
    "mega": "mega",
    "gigantamax": "gigantamax",
    "gmax": "gigantamax",
    # add more if you need them
}

# regexes for common formats
RE_PAREN = re.compile(r"^(?P<base>[\w\-\.\' ]+)\s*\(\s*(?P<form>[^)]+)\s*\)\s*$")
RE_PREFIX = re.compile(r"^(?P<form>[\w\-\.\' ]+)\s+(?P<base>[\w\-\.\' ]+)$")
RE_SUFFIX = re.compile(r"^(?P<base>[\w\-\.\' ]+)[\s\-\_:,]+(?P<form>[\w\-\.\' ]+)$")

def _clean_token(tok: str) -> str:
    if tok is None:
        return ""
    # remove extra punctuation, unify quotes, collapse spaces, lowercase
    return " ".join(tok.strip().replace(".", "").replace("’", "'").replace("`", "'").split()).lower()

def normalize_name(raw: str) -> Optional[str]:
    """
    Normalize raw Pokémon name to canonical output form used by the app.
    Rules:
      - 'Vulpix (Alolan)' -> 'alolan vulpix'
      - 'Alolan Vulpix'   -> 'alolan vulpix'
      - 'Vulpix-alolan'   -> 'alolan vulpix'
      - otherwise returns cleaned lowercase string (spaces preserved)
    Returns None if input is empty or invalid.
    """
    if not raw:
        return None
    s = raw.strip()
    if not s:
        return None

    # Parentheses form: "Vulpix (Alolan)"
    m = RE_PAREN.match(s)
    if m:
        base = _clean_token(m.group("base"))
        form = _clean_token(m.group("form"))
        form_tok = _VARIANT_MAP.get(form, form)
        return f"{form_tok} {base}".strip()

    # Prefix form: "Alolan Vulpix"
    m = RE_PREFIX.match(s)
    if m:
        form = _clean_token(m.group("form"))
        base = _clean_token(m.group("base"))
        # If form is a known variant, treat as variant prefix
        if form in _VARIANT_MAP or form in _VARIANT_MAP.values():
            form_tok = _VARIANT_MAP.get(form, form)
            return f"{form_tok} {base}".strip()
        # else, fallback: return the cleaned full string (lowercase)
        return f"{base} {form}".strip()

    # Suffix/dash/comma form: "Vulpix - Alolan" or "Vulpix, Alolan" or "Vulpix-alolan"
    m = RE_SUFFIX.match(s)
    if m:
        base = _clean_token(m.group("base"))
        form = _clean_token(m.group("form"))
        form_tok = _VARIANT_MAP.get(form, form)
        if base.endswith(form_tok):
            return base
        return f"{form_tok} {base}".strip()

    # fallback: cleaned single name lowercase
    return _clean_token(s)
