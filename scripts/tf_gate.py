"""The first-hour gate after the Token Factory key arrives: can this key call an NVIDIA vision model on a photo?

  .venv/bin/python scripts/tf_gate.py        -> prints the decision, writes docs/gate_result.json

1. Lists the models the key can call (/v1/models) and the NVIDIA ones; marks vision-capable ids (VL / Omni / vision).
2. Sends ONE dev-set screenshot (never a held-out one) to LLM_VISION_MODEL, else the first NVIDIA vision id, first
   with the strict JSON schema, then (if refused) json_object, then plain. Records what worked.
3. Decision:
   PHOTO      a vision call returned a usable JSON reading      -> continue with the screenshot plan (HANDOFF §P1)
   TEXT_ONLY  no NVIDIA vision id, or every vision call failed -> switch to the text fallback (P3+P2): set
              PROOF_VISION=0 in .env.local, measure scripts/intake_eval.py --set fallback_dev / fallback_heldout,
              and lead the video with the Korean/Japanese messages instead of the photo.
"""
import json, os, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env.local")
from openai import OpenAI
from agent.llm import TOKEN_FACTORY_URL, CallLog, TracedClient

key = os.getenv("NEBIUS_API_KEY") or sys.exit("No NEBIUS_API_KEY in .env.local")
raw = OpenAI(base_url=os.getenv("LLM_BASE_URL") or TOKEN_FACTORY_URL, api_key=key, timeout=120, max_retries=0)
ids = sorted(m.id for m in raw.models.list().data)
nv = [i for i in ids if "nvidia" in i.lower() or "nemotron" in i.lower()]
vis = [i for i in nv if any(w in i.lower() for w in ("vl", "omni", "vision"))]
want = os.getenv("LLM_VISION_MODEL")
cands = ([want] if want else []) + [v for v in vis if v != want]
print(f"{len(ids)} models; NVIDIA {len(nv)}: {nv}\nvision-capable NVIDIA: {vis}")
res = {"when": time.strftime("%Y-%m-%d %H:%M"), "all": ids, "nvidia": nv, "nvidia_vision": vis, "tries": [], "decision": "TEXT_ONLY"}
(ROOT / "docs/token_factory_models.json").write_text(json.dumps({"all": ids, "nvidia": nv, "nvidia_vision": vis}, indent=1))
man = [json.loads(l) for l in (ROOT / "docs/eval/screens/manifest.jsonl").read_text().splitlines() if l.strip()]
dev = next(m for m in man if m["split"] == "dev" and m["kind"] == "true")
from agent.proof import prepare_image, read_screen, check_fields
jpeg, _ = prepare_image((ROOT / "docs/eval/screens" / dev["clean_file"]).read_bytes())
for model in cands:
    for mode in ("json_schema", "json_object", "off"):
        os.environ["LLM_VISION_MODEL"], os.environ["LLM_VISION_JSON"] = model, mode
        c = TracedClient(raw, CallLog(), "Nebius Token Factory")
        r = read_screen(c, jpeg)
        f = check_fields(r["raw"]) if r.get("ok") else None
        t = {"model": model, "json_mode": r.get("json_mode"), "ok": bool(r.get("ok")), "error": r.get("error"),
             "ms": sum(x.get("ms") or 0 for x in c.log), "fields": {k: (f or {}).get(k) for k in ("amount", "date", "time", "card_last4", "status")},
             "gold": dev["gold"]}
        res["tries"].append(t); print(json.dumps(t, ensure_ascii=False))
        if r.get("ok") and f and f.get("payment_found"):
            res.update(decision="PHOTO", vision_model=model, json_mode=mode)
            break
    if res["decision"] == "PHOTO":
        break
(ROOT / "docs/gate_result.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
print("\nDECISION:", res["decision"], res.get("vision_model", ""), res.get("json_mode", ""))
if res["decision"] == "PHOTO":
    print(f"Put in .env.local:  LLM_VISION_MODEL={res['vision_model']}\n                    LLM_VISION_JSON={res['json_mode']}")
else:
    print("Switch to the text fallback (HANDOFF.md 'Gate'): PROOF_VISION=0 in .env.local, then the fallback_* sets.")
