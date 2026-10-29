"""Record one live second turn for the public demo (data/precomputed/followup_d05_1.json): the customer behind the
edited card alert answers "it was the 19th"; Lightning reads it, the ledger is checked again, the reply is rewritten.

  LLM_BUDGET_USD=4.5 .venv/bin/python scripts/precompute_followup.py
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
from agent.followup import investigate_followup
from agent import sql_backend

TEXT = "아 죄송해요, 19일 새벽이었어요. 날짜를 잘못 말했네요."
first = json.loads((ROOT / "data/precomputed/proof_d05.json").read_text())["result"]
ex = next(e for e in json.loads((ROOT / "app/proof_examples/examples.json").read_text()) if e["id"] == "d05")
prev = {"message": ex["message"], "fields": first["proof"]["fields"], "verdict": first["proof"]["verdict"],
        "reply": first.get("customer_reply"), "image_data_url": first["proof"].get("image_data_url")}
sql_backend._CACHE.clear()
t = time.time()
r = investigate_followup(prev, TEXT)
calls = r.get("model_calls") or []
bad = [c for c in calls if not c.get("ok")]
commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
meta = {"recorded_at": datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds"), "provider": "Nebius Token Factory",
        "models": sorted({c.get("model") for c in calls if c.get("model")}), "text": TEXT, "code_commit": commit,
        "wall_ms": int((time.time() - t) * 1000), "status": "ok" if calls and not bad else "MODEL CALL FAILED — rerun"}
(ROOT / "data/precomputed/followup_d05_1.json").write_text(json.dumps({"meta": meta, "result": r}, ensure_ascii=False, indent=1, default=str))
print(r["proof"]["verdict"], r.get("order_id"), r.get("broken"), meta["status"], meta["wall_ms"], "ms",
      [(c["role"], c.get("model"), c.get("ms")) for c in calls], "\nreply:", r.get("customer_reply"), "\nread:", r["followup"].get("read"))
