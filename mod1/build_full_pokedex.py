# build_full_pokedex.py
# Fetches all pokemon species from PokéAPI and builds a normalized pokedex.json
# - Includes major regional variants (alolan, galarian, hisuian, paldean, etc.)
# - Excludes Mega and Gigantamax forms (filters out names containing mega, gigantamax, gmax)
# - Normalizes names into '<variant> <base>' lowercase format compatible with your app
# - Adds field "gen": integer (1..9)
#
# Usage:
#   pip install requests
#   python build_full_pokedex.py
#
# Output: pokedex.json (list of {"name":"...", "gen": <int>})
#
# Notes:
# - The script is careful about retries and polite to PokeAPI. It may take a few minutes.
# - If you want to include or exclude more forms, edit VARIANT_ALLOW or EXCLUDE_TOKENS.

import requests
import time
import json
import sys
from typing import List, Dict
from urllib.parse import urljoin

BASE = "https://pokeapi.co/api/v2/"
SPECIES_LIST_URL = urljoin(BASE, "pokemon-species/?limit=20000")  # should return all species
OUT_FILE = "pokedex.json"

# tokens that indicate a form we DO NOT want (mega/gigantamax/gmax)
EXCLUDE_TOKENS = {"mega", "gigantamax", "gmax"}

# mapping generation name -> number
GEN_MAP = {
    "generation-i": 1, "generation-ii": 2, "generation-iii": 3, "generation-iv": 4,
    "generation-v": 5, "generation-vi": 6, "generation-vii": 7, "generation-viii": 8, "generation-ix": 9
}

# Variant normalization rules (extra tokens that should be canonicalized as prefixes)
VARIANT_CANON = {
    "alolan": "alolan",
    "alola": "alolan",
    "galarian": "galarian",
    "galar": "galarian",
    "hisuian": "hisuian",
    "hisuia": "hisuian",
    "paldean": "paldean",
    "paldea": "paldean",
    # others can be added
}

def clean_token(tok: str) -> str:
    if not tok:
        return ""
    return " ".join(tok.strip().replace(".", "").replace("’", "'").replace("`","'").split()).lower()

def normalize_from_api_name(poke_name: str) -> str:
    """
    Accepts names coming from PokeAPI like:
      - 'vulpix' -> 'vulpix'
      - 'vulpix-alola' or 'vulpix-alolan' or 'vulpix-alolan' -> 'alolan vulpix'
      - 'meowth-galar' -> 'galarian meowth'
    Fallback: returns cleaned lowercase (spaces preserved).
    """
    s = clean_token(poke_name)
    # Many PokeAPI names are hyphen-separated tokens. Try to detect variant tokens at end.
    parts = s.split("-")
    # if only one token, return it
    if len(parts) == 1:
        return parts[0]
    # If last token is a known variant (e.g. 'alola', 'alolan', 'galar', 'galarian', 'hisui', 'hisuian', 'paldea', 'paldean')
    last = parts[-1]
    # normalize last
    last_norm = VARIANT_CANON.get(last, last)
    # If last_norm maps to an exclude token (mega/gmax), let caller filter it out
    # Base name is everything before the last token joined (some names include hyphens legitimately, e.g., 'ho-oh' -> 'ho-oh')
    base = "-".join(parts[:-1])
    # convert base hyphens into spaces (for names like 'mr-mime' -> 'mr mime')
    base_clean = base.replace("-", " ").strip()
    # If last token isn't one of our variant tokens, try prefix detection: sometimes PokeAPI uses 'small' or 'plant' e.g., 'wormadam-sandy'
    if last_norm in VARIANT_CANON.values() or last in VARIANT_CANON:
        return f"{last_norm} {base_clean}"
    # Another heuristic: names like 'alolan-vulpix' (rare) => if first token is variant
    if parts[0] in VARIANT_CANON or parts[0] in VARIANT_CANON.values():
        first = VARIANT_CANON.get(parts[0], parts[0])
        rest = " ".join(parts[1:]).replace("-", " ")
        return f"{first} {rest}"
    # fallback: return fully cleaned string with hyphens replaced by spaces
    return s.replace("-", " ")

def should_exclude(name: str) -> bool:
    # Exclude if contains any exclude token (mega/gigantamax/gmax)
    lower = name.lower()
    for t in EXCLUDE_TOKENS:
        if t in lower:
            return True
    return False

def safe_get(url: str, retries=3, backoff=1.0):
    for attempt in range(1, retries+1):
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            return r
        except Exception as e:
            if attempt == retries:
                raise
            wait = backoff * attempt
            print(f"Warning: request failed ({e}), retrying in {wait:.1f}s...", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError("unreachable")

def main():
    print("Fetching species list from PokéAPI...")
    resp = safe_get(SPECIES_LIST_URL)
    data = resp.json()
    species_list = data.get("results", [])
    print(f"Found {len(species_list)} species entries (this may include many form variants).")

    out = []
    seen = set()  # (name, gen) dedupe

    for i, sp in enumerate(species_list, start=1):
        name = sp.get("name")
        url = sp.get("url")
        if not name or not url:
            continue
        try:
            sp_resp = safe_get(url)
            sp_json = sp_resp.json()
            gen_name = sp_json.get("generation", {}).get("name")
            gen_num = GEN_MAP.get(gen_name, 1)
            # species endpoint has 'varieties' which point to pokemon resources (which include variant names)
            varieties = sp_json.get("varieties") or []
            # Also include the base species name as entry (normalize it)
            for var in varieties:
                poke = var.get("pokemon", {})
                poke_name = poke.get("name")
                if not poke_name:
                    continue
                normalized = normalize_from_api_name(poke_name)
                # exclude megas/gmax/gigantamax
                if should_exclude(poke_name) or should_exclude(normalized):
                    # skip
                    continue
                # ensure normalized is in '<variant> <base>' or base form; keep lowercase
                normalized_clean = clean_token(normalized)
                key = (normalized_clean, gen_num)
                if key not in seen:
                    seen.add(key)
                    out.append({"name": normalized_clean, "gen": gen_num})
            # polite pause every few requests
            if i % 50 == 0:
                print(f"Processed {i}/{len(species_list)} species, collected {len(out)} entries so far...")
                time.sleep(0.5)
            else:
                # tiny sleep to be polite (PokeAPI is static-hosted but we still be kind)
                time.sleep(0.06)
        except Exception as e:
            print(f"Error fetching species {name} ({url}): {e}", file=sys.stderr)
            # continue with next one
            continue

    # Sort entries by gen then name
    out_sorted = sorted(out, key=lambda e: (e["gen"], e["name"]))
    print(f"Writing {len(out_sorted)} pokedex entries to {OUT_FILE}...")
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(out_sorted, f, indent=2, ensure_ascii=False)
    print("Done. pokedex.json written.")

if __name__ == "__main__":
    main()
