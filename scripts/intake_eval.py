"""Measure the intake step (Nemotron reads the message and plans the lookups) against hand-labelled messages,
next to the regex the agent used before. Writes a JSON log and appends a summary line to docs/measurements_nebius.md.

  .venv/bin/python scripts/intake_eval.py --set heldout --mode regex          # no key needed
  .venv/bin/python scripts/intake_eval.py --set heldout --mode model          # needs NEBIUS_API_KEY in .env.local
  .venv/bin/python scripts/intake_eval.py --set heldout --mode model --model nvidia/<another nemotron id>

Sets: docs/eval/intake_dev.jsonl (12, written by the builder, used while writing the prompt) and
docs/eval/intake_heldout.jsonl (40, written by a separate model that never saw the prompt or the code; run on it
only to report, never to tune). Each message is scored on:
  sender      the customer's own address (among several, sometimes)
  orders      the order numbers written in the message
  amount      the amount the customer says they paid (digits, 만/천, Korean number words)
  complaint   what they say went wrong (model only; the regex has no notion of it)
  end_to_end  the investigation lands on the right order and the right broken link (or finds nothing when it should)
  plan_hit    (model) the model's own plan reached that order without the fallback lookup
  dropped     (model) values the model returned that the message does not support (removed by ground())
"""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env.local")


def load(name):
    if name.startswith("fallback_"):  # docs/eval/text_fallback.jsonl: Korean/Japanese, long threads, attacks (split field)
        rows = [json.loads(l) for l in (ROOT / "docs/eval/text_fallback.jsonl").read_text().splitlines() if l.strip()]
        return [r for r in rows if r.get("split") == name.split("_", 1)[1]]
    return [json.loads(l) for l in (ROOT / f"docs/eval/intake_{name}.jsonl").read_text().splitlines() if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="heldout", choices=["dev", "heldout", "fallback_dev", "fallback_heldout"])
    ap.add_argument("--mode", default="regex", choices=["regex", "model"])
    ap.add_argument("--model", default="", help="override LLM_MODEL_INTAKE for this run")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    if a.model:
        os.environ["LLM_MODEL_INTAKE"] = a.model
    os.environ.setdefault("AGENT_LOOP", "0")  # measure the plan itself; the turn-by-turn loop is not used in the public demo
    from agent.investigator import investigate
    from agent.intake import regex_baseline
    from agent.llm import model_for
    from agent import sql_backend
    rows, t0 = [], time.time()
    items = load(a.set)[: a.limit or None]
    if a.mode == "model" and not (os.getenv("NEBIUS_API_KEY") or os.getenv("LLM_FAKE") == "1"):
        sys.exit("No NEBIUS_API_KEY: put it in .env.local (see HANDOFF.md).")
    for it in items:
        g = it["gold"]
        sql_backend._CACHE.clear()  # fresh synthetic data per message (no approvals carry over)
        use_model = a.mode == "model"
        r = investigate(it["message"], use_model=use_model)
        if use_model:
            gi = ((r.get("intake") or {}).get("grounded") or {})
            ph = (r.get("intake") or {}).get("placeholders") or {}
            from agent.intake import prepare
            _, mapping = prepare(it["message"])
            sender = mapping.get(gi.get("sender")) if gi.get("sender") else None
            got = {"sender_email": sender, "order_ids": gi.get("order_ids", []), "amount": (gi.get("amount") or {}).get("value"),
                   "complaint": gi.get("complaint"), "dropped": gi.get("dropped", []), "intake_ok": (r.get("intake") or {}).get("ok")}
        else:
            b = regex_baseline(it["message"])
            got = {"sender_email": b["first_raw_email"], "order_ids": b["order_ids"], "amount": (b["amount"] or {}).get("value"), "complaint": None, "dropped": []}
        if g["target_order"] is None:
            e2e = not r.get("ok")
        else:
            e2e = r.get("ok") and r.get("order_id") == g["target_order"] and r.get("broken") == g["expected_broken"]
        plan_hit = any(t["step"] == "plan" and f"reached {g['target_order']}" in t["detail"] for t in r.get("trace", [])) if g["target_order"] else None
        calls = r.get("model_calls") or []
        row = {"id": it["id"], "sender": got["sender_email"] == (g["sender_email"] or None),
               "orders": got["order_ids"] == g["order_ids"],
               "amount": got["amount"] == g["amount"], "complaint": (got["complaint"] == g["complaint"]) if got["complaint"] else None,
               "end_to_end": bool(e2e), "plan_hit": plan_hit, "dropped": len(got["dropped"]),
               "got": {k: got[k] for k in ("sender_email", "order_ids", "amount", "complaint")}, "found": [r.get("order_id"), r.get("broken")],
               "calls": len(calls), "ms": sum(c.get("ms") or 0 for c in calls), "tokens": sum((c.get("prompt_tokens") or 0) + (c.get("completion_tokens") or 0) for c in calls),
               "failed_calls": sum(1 for c in calls if not c.get("ok")),
               "escalated": any(c.get("role") == "escalate" for c in calls), "usd": sum(c.get("usd") or 0 for c in calls),
               "models": sorted({f"{c.get('role')}={c.get('model')}" for c in calls})}
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    n = len(rows)
    def pct(k):
        v = [x[k] for x in rows if x[k] is not None]
        return f"{sum(v)}/{len(v)}" if v else "—"
    label = (f"model {model_for('intake')} (Ultra re-read when unsure: {model_for('escalate')})" if os.getenv("LLM_ESCALATE", "1") != "0" else f"model {model_for('intake')}") if a.mode == "model" else "rules, no model"
    if os.getenv("LLM_FAKE") == "1":
        label = "FAKE dry run (not a model)"
    summary = {"when": time.strftime("%Y-%m-%d %H:%M"), "set": a.set, "n": n, "mode": label,
               "sender": pct("sender"), "orders": pct("orders"), "amount": pct("amount"), "complaint": pct("complaint"),
               "end_to_end": pct("end_to_end"), "plan_hit": pct("plan_hit") if a.mode == "model" else "—",
               "dropped_values": sum(x["dropped"] for x in rows), "failed_calls": sum(x["failed_calls"] for x in rows),
               "avg_model_ms": (sum(x["ms"] for x in rows) // n) if n else 0, "tokens": sum(x["tokens"] for x in rows),
               "escalated": sum(1 for x in rows if x["escalated"]), "usd": round(sum(x["usd"] for x in rows), 5),
               "wall_s": round(time.time() - t0, 1)}
    print(json.dumps(summary, ensure_ascii=False))
    out = ROOT / "docs/measurements"
    out.mkdir(exist_ok=True)
    tag = "fake" if os.getenv("LLM_FAKE") == "1" else a.mode
    (out / f"intake_{a.set}_{tag}_{time.strftime('%Y%m%d_%H%M')}.json").write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1))
    if os.getenv("LLM_FAKE") != "1":
        md = ROOT / "docs/measurements_nebius.md"
        if not md.exists():
            md.write_text("# Measurements (Nebius Token Factory version)\n\n| when | set | reader | sender | order nos. | amount | complaint | right order + link | plan reached it | dropped values | failed calls | avg model ms/msg | tokens |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")
        md.write_text(md.read_text() + "| {when} | {set} ({n}) | {mode} | {sender} | {orders} | {amount} | {complaint} | {end_to_end} | {plan_hit} | {dropped_values} | {failed_calls} | {avg_model_ms} | {tokens} |\n".format(**summary))


if __name__ == "__main__":
    main()
