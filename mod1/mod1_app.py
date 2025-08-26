# mod1/mod1_app.py
import os
import json
import logging
import traceback
from flask import Flask, request, render_template, jsonify

# ----- OPTIONAL: attempt to import your extra helper module(s) -----
# If you have mod1/mod1_modules/pokemon.py providing MINIMAL_POKEDEX or helpers,
# import it with a relative import. If it's missing, we'll fall back safely.
try:
    from .mod1_modules import pokemon as pkm
except Exception:
    pkm = None

# Minimal fallback pokedex (used only if pokedex.json missing or pkm missing)
MINIMAL_POKEDEX = [
    {"id": 1, "name": "Bulbasaur", "type": ["Grass", "Poison"], "generation": 1, "notes": ""},
    {"id": 4, "name": "Charmander", "type": ["Fire"], "generation": 1, "notes": ""},
    {"id": 7, "name": "Squirtle", "type": ["Water"], "generation": 1, "notes": ""},
]

# Create Flask app; templates/static live under mod1/templates and mod1/static
app = Flask(__name__, static_folder="static", template_folder="templates")

# Basic logging config (Vercel will show these logs)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Path to the JSON data file (inside the mod1 package)
POKEDEX_PATH = os.path.join(os.path.dirname(__file__), "pokedex.json")

def load_pokedex():
    """
    Load pokedex.json from the package. Returns a list of dicts.
    If the file is missing or malformed, falls back to (in this order):
      1) pkm.MINIMAL_POKEDEX if mod1_modules.pokemon exists and exposes it
      2) built-in MINIMAL_POKEDEX
    """
    # 1) Try to load file
    try:
        if os.path.exists(POKEDEX_PATH):
            with open(POKEDEX_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Normalize to a list of dicts
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                # Common formats: { "pokemon": [...] }, or id->obj
                for key in ("pokemon", "results", "data"):
                    if key in data and isinstance(data[key], list):
                        return data[key]
                # fallback: dict of id->obj
                return list(data.values())
    except Exception:
        # Log the JSON error for debugging; we'll fall back further down
        logger.exception("Failed reading or parsing pokedex.json")

    # 2) Try module-provided fallback
    try:
        if pkm and hasattr(pkm, "MINIMAL_POKEDEX"):
            return getattr(pkm, "MINIMAL_POKEDEX")
    except Exception:
        logger.exception("Error while using mod1_modules.pokemon fallback")

    # 3) Built-in fallback
    return MINIMAL_POKEDEX

@app.route("/", methods=["GET"])
def index():
    """
    Render main page. Supports optional query params:
      - q: search query (name, id, type)
      - gen: generation filter
    """
    try:
        pokedex = load_pokedex() or []
        # Read filter params
        q = (request.args.get("q") or "").strip().lower()
        gen = (request.args.get("gen") or "").strip()

        def matches_query(p):
            if not q:
                return True
            # check id
            try:
                if q == str(p.get("id", "")).lower():
                    return True
            except Exception:
                pass
            # name
            if q in str(p.get("name", "")).lower():
                return True
            # types
            types = p.get("type") or []
            if isinstance(types, (list, tuple)):
                types_text = " ".join(map(str, types)).lower()
            else:
                types_text = str(types).lower()
            if q in types_text:
                return True
            # notes or other fields
            if q in str(p.get("notes", "")).lower():
                return True
            return False

        filtered = [p for p in pokedex if matches_query(p)]
        if gen:
            filtered = [p for p in filtered if str(p.get("generation", "")).strip() == gen]

        # build unique generations list from the entire pokedex
        gens_set = { str(p.get("generation", "")).strip() for p in pokedex if p.get("generation") is not None }
        gens = sorted([g for g in gens_set if g != ""], key=lambda x: int(x) if x.isdigit() else x)

        return render_template(
            "index.html",
            pokedex=filtered,
            query=q,
            selected_gen=gen,
            gens=gens
        )
    except Exception:
        # Log the exception and either show a detailed trace (if debug enabled) or a generic 500.
        logger.exception("Unhandled exception in index route")
        if os.environ.get("SHOW_TRACEBACK") == "1":
            # show pretty traceback for debugging (REMOVE in production)
            tb = traceback.format_exc()
            return f"<pre>{tb}</pre>", 500
        return "Internal Server Error", 500

@app.route("/api/pokedex", methods=["GET"])
def api_pokedex():
    """
    Return the full pokedex JSON.
    """
    try:
        pokedex = load_pokedex()
        return jsonify({"count": len(pokedex), "results": pokedex})
    except Exception:
        logger.exception("Failed to serve /api/pokedex")
        return jsonify({"error": "failed to load pokedex"}), 500

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

# Helpful: return a small JSON when the app starts in local dev
@app.route("/api/info", methods=["GET"])
def info():
    return jsonify({
        "app": "mod1_pokedex",
        "pokedex_path": POKEDEX_PATH,
        "entries": len(load_pokedex())
    })

# If run locally, enable debug mode via FLASK_DEBUG env var or simply run python mod1/mod1_app.py
if __name__ == "__main__":
    debug_env = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug_env, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
