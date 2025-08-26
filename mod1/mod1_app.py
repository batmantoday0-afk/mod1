from flask import Flask, request, jsonify, render_template
import os
import json
from mod1_modules import pokemon as pkm

app = Flask(__name__)

POKEDEX_PATH = os.path.join(os.path.dirname(__file__), "pokedex.json")

def load_pokedex():
    if os.path.exists(POKEDEX_PATH):
        with open(POKEDEX_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return pkm.MINIMAL_POKEDEX

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/module1/upload", methods=["POST"])
def upload():
    """
    Accepts:
    - file: a .txt file with one pokemon name per line (optional)
    - text: pasted names (one per line) (optional)
    - manual: extra comma/newline-separated names (optional)
    - sh: 'on' to append --sh to every gen command (optional)
    Returns JSON:
    {
      "missing_by_gen": { "1": {"command": "...", "count": N, "missing": [...]}, ... },
      "combined_command": "..."
    }
    Note: This response intentionally does NOT include the 'owned' list.
    """
    sh_flag = False
    if request.form.get("sh") in ("on", "true", "1", "yes") or request.values.get("sh") in ("on", "true", "1", "yes"):
        sh_flag = True

    raw_lines = []
    # file upload (txt)
    if "file" in request.files and request.files["file"]:
        f = request.files["file"]
        try:
            content = f.read().decode("utf-8")
        except Exception:
            # fallback
            f.stream.seek(0)
            content = f.read().decode("latin-1", errors="ignore")
        raw_lines.extend([ln.strip() for ln in content.splitlines() if ln.strip()])

    # pasted text
    if request.form.get("text"):
        content = request.form.get("text")
        raw_lines.extend([ln.strip() for ln in content.splitlines() if ln.strip()])

    # manual extra entries; accept comma or newline separated
    manual = request.form.get("manual") or request.values.get("manual") or ""
    if manual:
        parts = [p.strip() for p in manual.replace(",", "\n").splitlines() if p.strip()]
        raw_lines.extend(parts)

    # raw body fallback
    if not raw_lines:
        try:
            raw = request.data.decode("utf-8")
            if raw.strip():
                raw_lines.extend([ln.strip() for ln in raw.splitlines() if ln.strip()])
        except Exception:
            pass

    # normalize input names and deduplicate
    normalized_owned = []
    seen = set()
    for raw in raw_lines:
        norm = pkm.normalize_name(raw)
        if not norm:
            continue
        if norm not in seen:
            seen.add(norm)
            normalized_owned.append(norm)

    pokedex = load_pokedex()
    gen_map = {}
    for entry in pokedex:
        gen = int(entry.get("gen", 1))
        name = pkm.normalize_name(entry["name"])
        gen_map.setdefault(gen, set()).add(name)

    # Build missing_by_gen but DO NOT return owned list
    missing_by_gen = {}
    for g in range(1, 10):
        all_names = sorted(list(gen_map.get(g, set())))
        missing = [n for n in all_names if n not in normalized_owned]
        # prefix each pokemon with --n as requested
        cmd_parts = []
        for nm in missing:
            cmd_parts.append(f"--n {nm}")
        cmd = " ".join(cmd_parts)
        if sh_flag and cmd.strip():
            cmd = f"{cmd} --sh"
        missing_by_gen[str(g)] = {
            "missing": missing,
            "count": len(missing),
            "command": cmd
        }

    combined_cmds = []
    for g in range(1, 10):
        cmd = missing_by_gen[str(g)]["command"]
        if cmd.strip():
            combined_cmds.append(cmd)
    combined_command = " && ".join(combined_cmds)

    return jsonify({
        "missing_by_gen": missing_by_gen,
        "combined_command": combined_command
    })

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
