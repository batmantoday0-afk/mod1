# mod1/mod1_app.py
import os
import json
from flask import Flask, request, render_template, jsonify

# Create Flask app; set static/template folders relative to this package
app = Flask(__name__, static_folder="static", template_folder="templates")

POKEDEX_PATH = os.path.join(os.path.dirname(__file__), "pokedex.json")

def load_pokedex():
    """
    Load pokedex.json from the mod1 folder.
    Returns a list of dicts (empty list on error).
    """
    try:
        if os.path.exists(POKEDEX_PATH):
            with open(POKEDEX_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Expect data to be a list; if dict, try to extract 'pokemon' or similar
                if isinstance(data, dict):
                    # try common keys
                    for key in ("pokemon", "results", "data"):
                        if key in data and isinstance(data[key], list):
                            return data[key]
                    # fallback: if dict of id->obj, return values
                    return list(data.values())
                if isinstance(data, list):
                    return data
        # fallback: empty list
        return []
    except Exception:
        # Avoid crashing on malformed JSON; return empty list instead
        return []

@app.route("/", methods=["GET"])
def index():
    pokedex = load_pokedex() or []
    q = (request.args.get("q") or "").strip().lower()
    gen = (request.args.get("gen") or "").strip()

    def matches_query(p):
        if not q:
            return True
        # id
        try:
            pid = str(p.get("id", "")).lower()
            if q == pid:
                return True
        except Exception:
            pass
        # name
        if q in str(p.get("name", "")).lower():
            return True
        # types (list)
        types_text = " ".join(p.get("type", []) or []).lower()
        if q in types_text:
            return True
        # notes/other fields
        if q in str(p.get("notes", "")).lower():
            return True
        return False

    # first filter by query
    filtered = [p for p in pokedex if matches_query(p)]
    # then by generation if provided
    if gen:
        filtered = [p for p in filtered if str(p.get("generation", "")).strip() == gen]

    # build unique gens list from the entire pokedex (not just filtered)
    gens_set = { str(p.get("generation", "")).strip() for p in pokedex if p.get("generation") is not None }
    gens = sorted([g for g in gens_set if g != ""], key=lambda x: int(x) if x.isdigit() else x)

    # Render template
    return render_template(
        "index.html",
        pokedex=filtered,
        query=q,
        selected_gen=gen,
        gens=gens
    )

@app.route("/api/pokedex", methods=["GET"])
def api_pokedex():
    """Return the full pokedex JSON (or limited view)."""
    pokedex = load_pokedex()
    return jsonify({"count": len(pokedex), "results": pokedex})

# Basic health-check
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    # Local dev convenience
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
