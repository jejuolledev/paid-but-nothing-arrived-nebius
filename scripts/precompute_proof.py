"""Record one live Token Factory run of each example photo for the public demo (data/precomputed/proof_<id>.json).
The page labels it "Recorded live run" and offers "Run it live now". Run LOCALLY on the Mac so the boxes (from
on-device OCR) are recorded too; the public server has no OCR and shows the table without boxes on live runs.

  .venv/bin/python scripts/precompute_proof.py
"""
import json, os, subprocess, sys, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env.local")
if os.getenv("LLM_FAKE") == "1" or not os.getenv("NEBIUS_API_KEY"):
    sys.exit("Needs a real NEBIUS_API_KEY (and not LLM_FAKE).")
os.environ.setdefault("AGENT_LOOP", "0")
from agent.proof import investigate_proof
from agent import sql_backend
from agent.llm import model_for

ex = json.loads((ROOT / "app/proof_examples/examples.json").read_text())
out = ROOT / "data/precomputed"; out.mkdir(parents=True, exist_ok=True)
commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
for e in ex:
    sql_backend._CACHE.clear()
    t = time.time()
    r = investigate_proof((ROOT / f"app/proof_examples/{e['id']}.jpg").read_bytes(), e["message"])
    calls = r.get("model_calls") or []
    bad = [c for c in calls if not c.get("ok")]
    status = "ok" if calls and not bad else "MODEL CALL FAILED — rerun" if bad else "NO MODEL CALL — check the key"
    meta = {"recorded_at": datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds"), "provider": "Nebius Token Factory",
            "models": sorted({c.get("model") for c in calls if c.get("model")}), "requested": {r_: model_for(r_) for r_ in ("vision", "intake", "explain", "reply")},
            "code_commit": commit, "wall_ms": int((time.time() - t) * 1000), "status": status}
    (out / f"proof_{e['id']}.json").write_text(json.dumps({"meta": meta, "result": r}, ensure_ascii=False, indent=1, default=str))
    print(e["id"], e["kind"], r["proof"]["verdict"], status, meta["wall_ms"], "ms", [(c["role"], c.get("model"), c.get("ms")) for c in calls])
