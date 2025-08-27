# mod1_modules/pokemon.py
"""
Normalization utilities for the command-generator app.

Behavior rules:
 - If there's a regional token, normalized output => "<regional> <form/extra> <pokemon>"
 - Else: "<form/feature> <pokemon>"
 - If no form/feature: "<pokemon>"
 - Use pokedex.json (if available next to the project root) to identify the canonical base name.
 - Preserve punctuation that matters in pokedex.json (e.g. "mr.", "sirfetch'd", "10% zygarde").
 - Output is lowercase and whitespace-collapsed.
"""

from typing import Optional, List, Tuple
import json
import re
from pathlib import Path

# Minimal fallback pokedex (keeps module usable if pokedex.json missing)
MINIMAL_POKEDEX = [
    {"name": "Bulbasaur", "gen": 1}, {"name": "Ivysaur", "gen": 1}, {"name": "Venusaur", "gen": 1},
    {"name": "Charmander", "gen": 1}, {"name": "Charmeleon", "gen": 1}, {"name": "Charizard", "gen": 1},
    {"name": "Squirtle", "gen": 1}, {"name": "Wartortle", "gen": 1}, {"name": "Blastoise", "gen": 1},
    {"name": "Pikachu", "gen": 1}, {"name": "Raichu", "gen": 1},
]

# Known region/variant tokens and canonical forms
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
}

# Regexes for common formats (allow dots/apostrophes/percent/hyphen)
RE_PAREN = re.compile(r"^(?P<base>[\w\-\.\' %]+)\s*\(\s*(?P<form>[^)]+)\s*\)\s*$")
RE_PREFIX = re.compile(r"^(?P<form>[\w\-\.\' %]+)\s+(?P<base>[\w\-\.\' %]+)$")
RE_SUFFIX = re.compile(r"^(?P<base>[\w\-\.\' %]+)[\s\-\_:,]+(?P<form>[\w\-\.\' %]+)$")

# Helpers to locate the pokedex.json file next to the package root
def _find_pokedex_path() -> Optional[str]:
    this_file = Path(__file__).resolve()
    candidate = this_file.parent.parent / "pokedex.json"
    if candidate.exists():
        return str(candidate)
    cwd_candidate = Path.cwd() / "pokedex.json"
    if cwd_candidate.exists():
        return str(cwd_candidate)
    return None

# Load pokedex names into a set for exact-match and subsequence matching
_POKEDEX_NAMES_SET = set()
_POKEDEX_LOADED = False

def _load_pokedex_names():
    global _POKEDEX_LOADED, _POKEDEX_NAMES_SET
    if _POKEDEX_LOADED:
        return
    path = _find_pokedex_path()
    if not path:
        # no file available; leave set empty and mark loaded
        _POKEDEX_NAMES_SET = set()
        _POKEDEX_LOADED = True
        return
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        names = set()
        if isinstance(data, list):
            for entry in data:
                if isinstance(entry, dict) and "name" in entry:
                    names.add(str(entry["name"]).strip().lower())
        elif isinstance(data, dict):
            if "pokemon" in data and isinstance(data["pokemon"], list):
                for entry in data["pokemon"]:
                    if isinstance(entry, dict) and "name" in entry:
                        names.add(str(entry["name"]).strip().lower())
            else:
                for v in data.values():
                    if isinstance(v, dict) and "name" in v:
                        names.add(str(v["name"]).strip().lower())
        _POKEDEX_NAMES_SET = names
    except Exception:
        _POKEDEX_NAMES_SET = set()
    _POKEDEX_LOADED = True

# Basic token cleaner: collapse whitespace, unify quotes, preserve dots/apostrophes/%
def _clean_token(tok: str) -> str:
    if tok is None:
        return ""
    s = tok.strip().replace("’", "'").replace("`", "'")
    s = " ".join(s.split())
    return s.lower()

# Split input into tokens (split on whitespace only)
def _tokens(s: str) -> List[str]:
    return [t for t in s.split() if t]

# Find the longest contiguous subsequence of tokens that matches a pokedex name.
# Returns (start_index, end_index, matched_name) or None.
def _find_base_from_tokens(tokens: List[str]) -> Optional[Tuple[int, int, str]]:
    _load_pokedex_names()
    if not _POKEDEX_NAMES_SET:
        return None
    n = len(tokens)
    for length in range(n, 0, -1):
        for start in range(0, n - length + 1):
            end = start + length
            phrase = " ".join(tokens[start:end])
            phrase_clean = _clean_token(phrase)
            if phrase_clean in _POKEDEX_NAMES_SET:
                return (start, end, phrase_clean)
    return None

def normalize_name(raw: str) -> Optional[str]:
    """
    Normalize raw Pokémon name per user's rules.

    - Use pokedex.json to detect the real base name when possible.
    - Output string will be lowercased, whitespace-collapsed.
    - Ordering:
        regional (if any) + form(s) (if any) + base
    - Does NOT invent facts: if pokedex contains a canonical string exactly, it will be returned unchanged.
    """
    if not raw:
        return None
    s = raw.strip()
    if not s:
        return None

    # unified punctuation
    s = s.replace("\u2019", "'").replace("\u2018", "'").replace("\u2013", "-")

    # EARLY EXACT-MATCH GUARD:
    # If the cleaned raw string exactly matches a pokedex entry, return that canonical form unchanged.
    _load_pokedex_names()
    if _POKEDEX_NAMES_SET:
        if s.strip().lower() in _POKEDEX_NAMES_SET:
            return s.strip().lower()

    # 1) Parentheses form: "Vulpix (Alolan)"
    m = RE_PAREN.match(s)
    if m:
        base_orig = m.group("base")
        form_orig = m.group("form")
        base = _clean_token(base_orig)
        form = _clean_token(form_orig)
        if form in _VARIANT_MAP:
            region = _VARIANT_MAP[form]
            return f"{region} {base}".strip()
        return f"{form} {base}".strip()

    # 2) Prefix: "Alolan Vulpix" or "Busted Mimikyu Totem"
    m = RE_PREFIX.match(s)
    if m:
        form_orig = m.group("form")
        base_orig = m.group("base")
        form = _clean_token(form_orig)
        base = _clean_token(base_orig)
        if form in _VARIANT_MAP:
            region = _VARIANT_MAP[form]
            return f"{region} {base}".strip()
        return f"{form} {base}".strip()

    # 3) Suffix/dash/comma: "Vulpix - Alolan" / "Vulpix, Alolan" / "Vulpix-alolan"
    m = RE_SUFFIX.match(s)
    if m:
        base_orig = m.group("base")
        form_orig = m.group("form")
        base = _clean_token(base_orig)
        form = _clean_token(form_orig)
        if form in _VARIANT_MAP:
            region = _VARIANT_MAP[form]
            return f"{region} {base}".strip()
        return f"{form} {base}".strip()

    # 4) Token-based approach: find base by matching subsequence against pokedex
    toks = [_clean_token(t) for t in _tokens(s)]
    if not toks:
        return None

    # detect region tokens anywhere, remember the first one (canonicalized), remove it from tokens for base search
    region_token = None
    tokens_no_region = []
    for t in toks:
        if t in _VARIANT_MAP:
            if not region_token:
                region_token = _VARIANT_MAP[t]
            # skip adding this token to tokens_no_region (we'll place region later)
        else:
            tokens_no_region.append(t)

    base_match = _find_base_from_tokens(tokens_no_region)
    if base_match:
        start, end, base_name = base_match
        forms = tokens_no_region[:start] + tokens_no_region[end:]
        if forms:
            forms_part = " ".join(forms).strip()
            if region_token:
                return f"{region_token} {forms_part} {base_name}".strip()
            else:
                return f"{forms_part} {base_name}".strip()
        else:
            if region_token:
                return f"{region_token} {base_name}".strip()
            return base_name

    # 5) Fallback heuristics (safe, conservative)
    if region_token:
        remainder = " ".join(tokens_no_region).strip()
        if remainder:
            return f"{region_token} {remainder}".strip()
        else:
            return region_token

    if len(tokens_no_region) == 1:
        return tokens_no_region[0]
    else:
        forms_part = " ".join(tokens_no_region[:-1]).strip()
        base_guess = tokens_no_region[-1]
        if forms_part:
            return f"{forms_part} {base_guess}".strip()
        return base_guess

# Export
__all__ = ["normalize_name", "MINIMAL_POKEDEX"]
