"""Measure the screenshot step on the frozen screenshot set (docs/eval/screens/manifest.jsonl): who reads the photo
(free on-device OCR + rules, or a Nemotron vision model on Token Factory), then the same deterministic ledger check.

  .venv/bin/python scripts/proof_eval.py --mode ocr-current   --set heldout     # OCR + today's rules (no key)
  .venv/bin/python scripts/proof_eval.py --mode ocr-keyword   --set heldout     # OCR + payment-word rules (no key)
  .venv/bin/python scripts/proof_eval.py --mode model         --set dev         # Nemotron VL; tune ONLY on dev
  .venv/bin/python scripts/proof_eval.py --mode model         --set heldout     # report once, never tune on it
  options: --variant photo|clean  --model <vision id>  --json-mode json_schema|json_object|off  --limit N

Scores per image: amount, date+time (minute), card last-4, status class, verdict (ledger_match / no_matching_payment /
not_paid), and verdict with the fields right (a doctored image "caught" because the reader misread it is not counted
as a catch). Writes docs/measurements/proof_*.json and appends a row to docs/measurements.md.
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env.local")
SCREENS = ROOT / "docs/eval/screens"
CACHE = ROOT / "build/ocr_cache.json"


def load(split):
    items = [json.loads(l) for l in (SCREENS / "manifest.jsonl").read_text().splitlines() if l.strip()]
    return [i for i in items if i["split"] == split]


def ocr_cached(jpeg: bytes, cache: dict) -> dict | None:
    from agent import ocr
    k = hashlib.sha256(jpeg).hexdigest()
    if k not in cache:
        if not ocr.available():
            return None
        cache[k] = ocr.ocr_bytes(jpeg)
    return cache[k]


def status_class(s):
    return "paid" if s in ("approved", "paid") else ("unpaid" if s in ("pending", "cancelled", "failed", "refunded") else "unknown")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="heldout", choices=["dev", "heldout"])
    ap.add_argument("--mode", default="ocr-keyword", choices=["ocr-current", "ocr-keyword", "model", "model-ocrtext"])
    ap.add_argument("--variant", default="photo", choices=["photo", "clean"])
    ap.add_argument("--model", default="")
    ap.add_argument("--json-mode", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-redact", action="store_true", help="send the photo without the OCR blur step")
    a = ap.parse_args()
    if a.model:
        os.environ["LLM_VISION_MODEL"] = a.model
    if a.json_mode:
        os.environ["LLM_VISION_JSON"] = a.json_mode
    from agent.proof import prepare_image, redact, read_screen, check_fields, decide
    from agent.screen_rules import rules_current, rules_keyword
    from agent.sql_backend import DuckDBBackend
    from agent.tools import Tools
    from agent.llm import token_factory_client, model_for, CallLog
    client = None
    if a.mode.startswith("model"):
        client, why = token_factory_client(CallLog(), timeout=float(os.getenv("LLM_TIMEOUT", "120")))
        if client is None:
            sys.exit(f"No vision model client ({why}). Put NEBIUS_API_KEY in .env.local (HANDOFF.md).")
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    tools = Tools(DuckDBBackend())
    rows, t0 = [], time.time()
    for it in load(a.set)[: a.limit or None]:
        path = SCREENS / (it["file"] if a.variant == "photo" else it["clean_file"])
        jpeg, _ = prepare_image(path.read_bytes())
        ocr = ocr_cached(jpeg, cache) if (a.mode != "model" or not a.no_redact) else None
        if a.mode == "model-ocrtext" and ocr is None:
            sys.exit("model-ocrtext needs on-device OCR (macOS)")
        info = {}
        if a.mode.startswith("model"):
            if ocr and not a.no_redact:
                jpeg, _ = redact(jpeg, ocr)
            n0 = len(client.log)
            if a.mode == "model-ocrtext":
                from agent.ocr import text_of
                r = read_screen(client, None, ocr_text=text_of(ocr))
            else:
                r = read_screen(client, jpeg)
            f = check_fields(r["raw"], ocr) if r.get("ok") else None
            calls = client.log[n0:]
            info = {"ok": r.get("ok"), "error": r.get("error"), "json_mode": r.get("json_mode"), "model": r.get("model"),
                    "ms": sum(c.get("ms") or 0 for c in calls), "tokens": sum((c.get("prompt_tokens") or 0) + (c.get("completion_tokens") or 0) for c in calls),
                    "usd": sum(c.get("usd") or 0 for c in calls), "raw": r.get("raw")}
        else:
            if ocr is None:
                sys.exit("On-device OCR is not available (macOS only): build/ocr_vision")
            f = check_fields((rules_current if a.mode == "ocr-current" else rules_keyword)(ocr))
        g = it["gold"]
        d = decide(f, tools.find_payments(it["sender_email"]))
        gd, gt = g["paid_at_local"][:10], g["paid_at_local"][11:16]
        fd = (f or {}).get("date") or ""
        amount_ok = bool(f) and f.get("amount") == g["amount"]
        time_ok = bool(f) and f.get("time") == gt and (fd == gd or (len(fd) == 5 and gd.endswith(fd)))
        last4_ok = (bool(f) and f.get("card_last4") == g.get("card_last4")) if g.get("card_last4") else None
        status_ok = bool(f) and status_class(f.get("status")) == status_class(g.get("status"))
        verdict_ok = d["verdict"] == it["expected_verdict"]
        strict = verdict_ok and (it["kind"] == "unpaid" or (amount_ok and time_ok))
        row = {"id": it["id"], "kind": it["kind"], "lang": it["lang"], "style": it["style"], "difficulty": it.get("difficulty"),
               "amount": amount_ok, "time": time_ok, "last4": last4_ok, "status": status_ok, "verdict": verdict_ok, "verdict_strict": strict,
               "got": {k: (f or {}).get(k) for k in ("amount", "date", "time", "card_last4", "status")}, "gold": g, "verdict_got": d["verdict"],
               "expected": it["expected_verdict"], **info}
        rows.append(row)
        print(json.dumps({k: row[k] for k in ("id", "kind", "amount", "time", "verdict", "verdict_strict", "got", "verdict_got")}, ensure_ascii=False), flush=True)
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps(cache))

    def frac(key, kinds=None):
        v = [r[key] for r in rows if r[key] is not None and (kinds is None or r["kind"] in kinds)]
        return f"{sum(v)}/{len(v)}" if v else "—"
    label = {"ocr-current": "macOS Vision OCR + today's rules", "ocr-keyword": "macOS Vision OCR + payment-word rules",
             "model": f"{model_for('vision')} on Token Factory",
             "model-ocrtext": f"{model_for('vision')} given only the OCR text (no image)"}[a.mode]
    if os.getenv("LLM_FAKE") == "1" and a.mode.startswith("model"):
        label = "FAKE dry run (not a model)"
    n = len(rows)
    summary = {"when": time.strftime("%Y-%m-%d %H:%M"), "set": a.set, "variant": a.variant, "n": n, "reader": label,
               "amount": frac("amount"), "time": frac("time"), "last4": frac("last4"), "status": frac("status"),
               "verdict": frac("verdict"), "verdict_true": frac("verdict", ("true",)), "verdict_doctored": frac("verdict", ("doctored",)),
               "verdict_unpaid": frac("verdict", ("unpaid",)), "verdict_strict": frac("verdict_strict"),
               "failed_calls": sum(1 for r in rows if r.get("ok") is False),
               "avg_ms": (sum(r.get("ms") or 0 for r in rows) // n) if n and a.mode.startswith("model") else None,
               "usd": round(sum(r.get("usd") or 0 for r in rows), 5) if a.mode.startswith("model") else None,
               "wall_s": round(time.time() - t0, 1)}
    print(json.dumps(summary, ensure_ascii=False))
    out = ROOT / "docs/measurements"
    out.mkdir(exist_ok=True)
    tag = "fake" if (os.getenv("LLM_FAKE") == "1" and a.mode.startswith("model")) else a.mode
    (out / f"proof_{a.set}_{a.variant}_{tag}_{time.strftime('%Y%m%d_%H%M')}.json").write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1))
    if tag != "fake":
        md = ROOT / "docs/measurements.md"
        head = "| when | set | photo | reader | amount | date+time | card last-4 | status | verdict | true → match | doctored → not in ledger | unpaid → not paid | verdict with fields right | failed calls | avg ms | USD |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        txt = md.read_text() if md.exists() else ""
        if "## Screenshot proof runs" not in txt:
            txt += "\n## Screenshot proof runs (appended by scripts/proof_eval.py)\n\n" + head
        txt += "| {when} | {set} ({n}) | {variant} | {reader} | {amount} | {time} | {last4} | {status} | {verdict} | {verdict_true} | {verdict_doctored} | {verdict_unpaid} | {verdict_strict} | {failed_calls} | {avg_ms} | {usd} |\n".format(
            **{k: ("—" if v is None else v) for k, v in summary.items()})
        md.write_text(txt)


if __name__ == "__main__":
    main()
