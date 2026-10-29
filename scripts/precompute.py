"""Record one live Token Factory run of each example case for the public demo, so judges see a result at once
(the page labels it "Recorded live run", with the time, and offers "Run it live now").

  .venv/bin/python scripts/precompute.py         -> data/precomputed/case1.json … case6.json

Refuses to run with LLM_FAKE=1 or without NEBIUS_API_KEY. Rerun after any change to the agent code.
"""
import json, os, re, subprocess, sys, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env.local")
if os.getenv("LLM_FAKE") == "1" or not os.getenv("NEBIUS_API_KEY"):
    sys.exit("Needs a real NEBIUS_API_KEY (and not LLM_FAKE).")
os.environ.setdefault("AGENT_LOOP", "0")  # same as the public demo
from agent.investigator import investigate
from agent import sql_backend
from agent.llm import model_for

html = (ROOT / "app/index.html").read_text()
EXAMPLES = {int(n): json.loads('"' + s.replace("\\'", "'") + '"') for n, s in re.findall(r"\n\s*(\d):\{label:'(?:[^'\\]|\\.)*',send:'((?:[^'\\]|\\.)*)'\}", html)}
assert len(EXAMPLES) == 6, EXAMPLES
out = ROOT / "data/precomputed"
out.mkdir(parents=True, exist_ok=True)
commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
ONLY = {int(x) for x in sys.argv[1:]}   # optional: case numbers to record again
for n, msg in EXAMPLES.items():
    if ONLY and n not in ONLY:
        continue
    sql_backend._CACHE.clear()
    t = time.time()
    r = investigate(msg)
    calls = r.get("model_calls") or []
    bad = [c for c in calls if not c.get("ok")]
    status = "ok" if calls and not bad else "MODEL CALL FAILED — rerun" if bad else "NO MODEL CALL — check the key"
    meta = {"recorded_at": datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds"), "provider": "Nebius Token Factory",
            "models": sorted({c.get("model") for c in calls if c.get("model")}), "requested": {"intake": model_for("intake"), "explain": model_for("explain")},
            "code_commit": commit, "wall_ms": int((time.time() - t) * 1000), "status": status}
    (out / f"case{n}.json").write_text(json.dumps({"meta": meta, "result": r}, ensure_ascii=False, indent=1, default=str))
    print(n, r.get("order_id"), r.get("broken"), status, meta["wall_ms"], "ms", [(c["role"], c.get("ms"), c.get("prompt_tokens"), c.get("completion_tokens")) for c in calls])
