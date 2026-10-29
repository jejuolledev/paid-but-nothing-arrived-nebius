"""What the customer says vs what the records show. Deterministic: the model only read the claims out of the
message (agent/intake.py); this code lines each one up against the rows of the order's journey."""
from __future__ import annotations
import re

_PACKS = {"lite10": ("lite", 10), "std30": ("standard", 30), "fam60": ("family", 60)}


COMPLAINT_WORDS = {"not_received": "nothing arrived", "charged_twice": "charged twice", "credited_twice": "credited twice",
                   "no_email": "no email", "not_sure_paid": "not sure the payment went through"}


def _date_from(words: str) -> str | None:
    """'2026-10-13', '10/13', '10월 13일', 'Oct 13' -> '-10-13'. Relative words ('yesterday') -> None."""
    w = words.lower()
    m = re.search(r"\d{4}-(\d{2})-(\d{2})", w) or re.search(r"\b(\d{1,2})/(\d{1,2})\b", w) or re.search(r"(\d{1,2})월\s*(\d{1,2})일", w)
    if m:
        return f"-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    m = re.search(r"\b(" + "|".join(months) + r")[a-z]*\.?\s+(\d{1,2})\b", w)
    if m:
        return f"-{months.index(m.group(1)) + 1:02d}-{int(m.group(2)):02d}"
    m = re.search(r"(?<!\d)(\d{1,2})\s*(?:일|日)", w)   # day only ("20일에 결제했어요"): compared with the day of the month
    if m and 1 <= int(m.group(1)) <= 31:
        return f"-{int(m.group(1)):02d}"
    return None


def _local_date(iso) -> str:
    """The ledger stores UTC; customers say the local (KST/JST) date."""
    try:
        from .proof import _local
        return _local(str(iso)).strftime("%Y-%m-%d")
    except Exception:
        return str(iso or "")[:10]


def compare_claims(intake: dict | None, journey: dict, verdict) -> list[dict]:
    """Rows of {claim, says, records, result: match | differs | unchecked, refs, note}."""
    if not intake:
        return []
    out = []
    pays = [p for p in journey.get("payments", []) if str(p.get("status", "")).upper() == "PAID"]
    orders = journey.get("orders", [])
    grants = [g for g in journey.get("grants", []) if g.get("status") == "granted"]
    a = intake.get("amount")
    if a:
        if pays:
            p = pays[-1]
            same = str(a["value"]) == str(p.get("amount")) and a.get("currency", "KRW") == str(p.get("currency", "KRW")).upper()
            out.append({"claim": "amount paid", "says": f"{a['value']:,} {a.get('currency', 'KRW')}",
                        "records": f"{int(p['amount']):,} {p.get('currency')} PAID", "result": "match" if same else "differs",
                        "refs": [p["ref"]], "note": "" if same else "The customer may be describing a different charge; ask for the receipt before acting."})
        elif orders:
            o = orders[0]
            out.append({"claim": "amount paid", "says": f"{a['value']:,} {a.get('currency', 'KRW')}",
                        "records": f"no charge at the payment provider (order price {int(o['amount']):,})", "result": "differs",
                        "refs": [o["ref"]], "note": "Nothing was charged for this order."})
    when = intake.get("paid_when")
    if when and pays:
        d = _date_from(when)
        p = pays[-1]
        loc = _local_date(p.get("created_at", ""))
        if d:
            same = loc.endswith(d)
            out.append({"claim": "paid on", "says": when, "records": loc, "result": "match" if same else "differs", "refs": [p["ref"]], "note": ""})
        else:
            out.append({"claim": "paid on", "says": when, "records": loc, "result": "unchecked", "refs": [p["ref"]],
                        "note": "Relative date; the message date is not known here."})
    pack = intake.get("pack")
    if pack and orders:
        key = str(orders[0].get("reward_key", ""))
        name, credits = _PACKS.get(key, (key, None))
        low = pack.lower()
        said_n = re.findall(r"\d+", low)
        same = (name in low) or (credits is not None and str(credits) in said_n) or key in low
        out.append({"claim": "pack", "says": pack, "records": f"{key} ({credits} credits)" if credits else key,
                    "result": "match" if same else "differs", "refs": [orders[0]["ref"]], "note": ""})
    c = intake.get("complaint")
    if c and c != "other":
        expect = {"not_received": {"order_created", "account_mismatch"},
                  "charged_twice": {"credit_granted"}, "credited_twice": {"credit_granted"},
                  "no_email": {"mail_delivered", "account_mismatch"}, "not_sure_paid": {None, "order_created"}}.get(c, set())
        records = verdict.headline
        same = verdict.broken in expect
        note = ""
        if c == "charged_twice" and not same:
            note = "Records show one charge."
        elif c == "charged_twice":
            note = "One charge; the credits were granted twice (the customer may call this a double charge)."
        if c == "not_received" and verdict.broken is None and not pays:
            note = "No charge exists, so nothing was owed."
        elif c == "not_received" and verdict.broken is None and grants:
            note = "The credits are in the account; the customer may not have looked."
        out.append({"claim": "what went wrong", "says": COMPLAINT_WORDS.get(c, c.replace("_", " ")), "records": records,
                    "result": "match" if same else "differs", "refs": [], "note": note})
    return out
