"""Self-check for docs/eval/screens/manifest.jsonl against the ledger CSVs.

usage: .venv/bin/python scripts/eval_screens/verify_manifest.py
Exits non-zero on any failure.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCR = ROOT / "docs/eval/screens"
KST = timedelta(hours=9)
# real KR/JP banks, card companies and pay apps that must not appear anywhere in the set
BRANDS = ["kakao", "toss", "naver", "payco", "samsung", "shinhan", "hyundai", "lotte", "woori", "hana bank",
          "kb국민", "국민은행", "국민카드", "신한", "삼성카드", "현대카드", "롯데카드", "우리은행", "우리카드", "하나은행",
          "하나카드", "농협", "nh", "카카오", "토스", "네이버페이", "페이코", "비씨카드", "bc카드", "기업은행",
          "paypay", "rakuten", "楽天", "三井住友", "jcb", "smbc", "mufg", "三菱", "みずほ", "line pay", "linepay",
          "d払い", "au pay", "aupay", "イオン", "セゾン", "visa", "mastercard", "apple pay", "google pay"]

fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


pays = list(csv.DictReader(open(ROOT / "data/out/payments.csv")))
orders = {r["order_id"]: r for r in csv.DictReader(open(ROOT / "data/out/orders.csv"))}
by_id = {p["payment_id"]: p for p in pays}
ms = [json.loads(l) for l in open(SCR / "manifest.jsonl")]


def local_of(p):
    return datetime.strptime(p["created_at"], "%Y-%m-%dT%H:%M:%SZ") + KST


def parse_local(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S" if s.count(":") == 2 else "%Y-%m-%d %H:%M")


ids = set()
for m in ms:
    sid = m["id"]
    check(sid not in ids, f"{sid}: duplicate id")
    ids.add(sid)
    for k in ("file", "clean_file"):
        check((SCR / m[k]).is_file(), f"{sid}: missing {m[k]}")
    g = m["gold"]
    check(g["currency"] == "KRW" and g["utc_offset"] == "+09:00" and g["merchant"] == "MOAHUB", f"{sid}: gold constants")
    shown = parse_local(g["paid_at_local"])
    if m["kind"] == "true":
        p = by_id.get(m["ledger_payment_id"])
        check(p is not None, f"{sid}: ledger_payment_id not found")
        if p:
            lt = local_of(p)
            check(int(p["amount"]) == g["amount"], f"{sid}: amount {g['amount']} != ledger {p['amount']}")
            check(lt.strftime("%Y-%m-%d %H:%M") == shown.strftime("%Y-%m-%d %H:%M"), f"{sid}: minute mismatch {shown} vs {lt}")
            if g["paid_at_local"].count(":") == 2:
                check(lt == shown, f"{sid}: seconds mismatch")
            check(p["card_last4"] == g["card_last4"], f"{sid}: last4")
            check(p["customer_email"] == m["sender_email"], f"{sid}: payer email != sender")
            check(p["status"] == "PAID" and g["status"] == "approved", f"{sid}: status")
        check(m["expected_verdict"] == "ledger_match" and m["doctored"] is None, f"{sid}: verdict/doctored")
    elif m["kind"] == "unpaid":
        check(m["ledger_payment_id"] is None and m["expected_verdict"] == "not_paid", f"{sid}: unpaid fields")
        check(g["status"] in ("pending", "cancelled") and g["card_last4"] is None, f"{sid}: unpaid gold")
        check(not any(p["customer_email"] == m["sender_email"] for p in pays), f"{sid}: sender has a payment")
        o = [o for o in orders.values() if o["email"] == m["sender_email"]]
        check(len(o) == 1 and o[0]["payment_id"] == "" and int(o[0]["amount"]) == g["amount"], f"{sid}: order row")
        if o:
            ol = datetime.strptime(o[0]["created_at"], "%Y-%m-%dT%H:%M:%SZ") + KST
            check(ol.strftime("%Y-%m-%d %H:%M") == shown.strftime("%Y-%m-%d %H:%M"), f"{sid}: order time")
    elif m["kind"] == "doctored":
        check(m["ledger_payment_id"] is None and m["expected_verdict"] == "no_matching_payment", f"{sid}: doctored fields")
        d = m["doctored"]
        check(d and d["from"] and d["to"] and d["patches"], f"{sid}: doctored record")
        hit = [p for p in pays if p["customer_email"] == m["sender_email"] and int(p["amount"]) == g["amount"]
               and abs(local_of(p) - shown) <= timedelta(minutes=10)]
        check(not hit, f"{sid}: doctored claim matches ledger row {hit}")
        # stricter: nobody at all paid that amount within +-10 min with that card
        hit2 = [p for p in pays if int(p["amount"]) == g["amount"] and p["card_last4"] == g["card_last4"]
                and abs(local_of(p) - shown) <= timedelta(minutes=10)]
        check(not hit2, f"{sid}: doctored claim matches some ledger row {hit2}")
        # the untouched fields must still be the true payment's values
        own = [p for p in pays if p["customer_email"] == m["sender_email"]]
        check(len(own) == 1, f"{sid}: sender should have exactly one payment")
        if own:
            p = own[0]
            check(p["card_last4"] == g["card_last4"], f"{sid}: last4 changed")
            if "amount" not in d["to"]:
                check(int(p["amount"]) == g["amount"], f"{sid}: amount should be untouched")
            check(d["from"].get("amount", int(p["amount"])) == int(p["amount"]), f"{sid}: from.amount not ledger")
    else:
        check(False, f"{sid}: bad kind {m['kind']}")
    check(m["difficulty"] in ("easy", "medium", "hard"), f"{sid}: difficulty")
    check(m["sender_email"] in m["message"], f"{sid}: message lacks sender email")
    check(len(m["distractors"]) >= 3, f"{sid}: too few distractors")


def count(split, kind=None):
    return sum(1 for m in ms if m["split"] == split and (kind is None or m["kind"] == kind))


check(count("heldout") == 16, "heldout must have 16 images")
check(count("heldout", "true") + count("heldout", "unpaid") == 8, "heldout must have 8 true incl. unpaid")
check(count("heldout", "unpaid") >= 1, "heldout needs >=1 unpaid")
check(count("heldout", "doctored") == 8, "heldout must have 8 doctored")
check(count("dev") == 6, "dev must have 6 images")
held = [m for m in ms if m["split"] == "heldout"]
check(sum(m["lang"] == "ja" for m in held) >= 2 and len({m["style"] for m in held if m["lang"] == "ja"}) >= 2, "ja styles")
check(len({m["style"] for m in held if m["lang"] == "ko"}) >= 3, "ko styles")
check(sum(m["difficulty"] == "hard" for m in held) >= 3, "need >=3 hard heldout images")
check((SCR / "contact_heldout.jpg").is_file() and (SCR / "contact_dev.jpg").is_file(), "contact sheets")

# brand scan over everything that could leak into images or text
texts = [(SCR / "manifest.jsonl").read_text()]
for p in (ROOT / "scripts/eval_screens/templates").glob("*"):
    texts.append(p.read_text())
texts.append((ROOT / "scripts/eval_screens/build.py").read_text())
tf = ROOT / "docs/eval/text_fallback.jsonl"
if tf.exists():
    texts.append(tf.read_text())
blob = "\n".join(texts).lower()
for b in BRANDS:
    if re.search(r"(?<![a-z])" + re.escape(b) + r"(?![a-z])", blob):
        fails.append(f"brand string found: {b}")

if fails:
    print("FAIL")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print(f"OK: {len(ms)} images (heldout {count('heldout')}: true {count('heldout','true')}, "
      f"unpaid {count('heldout','unpaid')}, doctored {count('heldout','doctored')}; dev {count('dev')})")
