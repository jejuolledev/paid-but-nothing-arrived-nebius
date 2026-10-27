"""Rules over OCR text of a payment screenshot: the no-model baselines for the photo step.

Two baselines, both written before any vision model was run and before the screenshot eval set was looked at:
  current   what the agent's existing rules do with text: the largest amount (intake.regex_baseline) and the first
            date/time in reading order. This is what "OCR + today's rules" means in docs/measurements.md.
  keyword   a fairer, stronger baseline: the amount on a line next to a payment word (결제/승인/ご利用/お支払い/
            amount …), away from balance/points/instalment/conversion words, near the merchant line; the date and
            time closest to that line, ignoring the phone's status-bar clock; card last-4 next to a mask.
Both return the same field dict as the vision model (agent/proof.py) so the verifier treats them identically.
"""
from __future__ import annotations
import re

PAY_KW = re.compile(r"결제|승인|이용\s*금액|금액|출금|사용|합계|ご利用|利用金額|利用額|お支払|支払|決済|承認|請求|金額|amount|paid|charged|payment|total", re.I)
BAD_KW = re.compile(r"잔액|잔고|残高|포인트|ポイント|적립|캐시백|할부|分割|回払|換算|約|円|¥|￥|JPY|한도|限度|balance|points?\b|cashback|이자|혜택|쿠폰|クーポン|광고|広告|\bAD\b|이벤트|キャンペーン|최대|최소|limit", re.I)
KRW_MARK = re.compile(r"원|₩|KRW|ウォン|won", re.I)
MERCHANT = re.compile(r"MOAHUB|모아허브|ＭＯＡＨＵＢ", re.I)
AMOUNT_RE = re.compile(r"(?<![\d.:/-])(\d{1,3}(?:[,，]\d{3})+|\d{4,8})(?![\d:/])")
TIME_RE = re.compile(r"(오전|오후|午前|午後|AM|PM)?\s*(\d{1,2})\s*[:：]\s*(\d{2})(?:\s*[:：]\s*(\d{2}))?\s*(AM|PM)?", re.I)
DATE_RE = re.compile(r"(?:(20\d{2})\s*[.\-/年]\s*)?(\d{1,2})\s*(?:[.\-/]|月)\s*(\d{1,2})\s*日?|(?:(20\d{2})\s*년\s*)?(\d{1,2})\s*월\s*(\d{1,2})\s*일")
LAST4_RE = re.compile(r"(?:[*＊•●xX]{2,}[\s-]*|末尾\s*|끝자리\s*|下4桁\s*|카드\s*\(\s*|\(\s*)(\d{4})(?!\d)")
STATUS = [("cancelled", re.compile(r"취소|キャンセル|取消|cancel", re.I)), ("failed", re.compile(r"실패|失敗|거절|declin|fail", re.I)),
          ("pending", re.compile(r"대기|진행\s*중|保留|処理中|未完了|pending|processing", re.I)),
          ("approved", re.compile(r"승인|결제\s*완료|완료|承認|確定|完了|approved|paid|success", re.I))]


def _num(s: str) -> int:
    return int(re.sub(r"[,，]", "", s))


def times_in(text: str) -> list[tuple[str, tuple[int, int]]]:
    out = []
    for m in TIME_RE.finditer(text):
        h, mi = int(m.group(2)), int(m.group(3))
        ampm = (m.group(1) or m.group(5) or "").lower()
        if ampm in ("오후", "午後", "pm") and h < 12:
            h += 12
        if ampm in ("오전", "午前", "am") and h == 12:
            h = 0
        if h < 24 and mi < 60:
            out.append((f"{h:02d}:{mi:02d}", m.span()))
    return out


def dates_in(text: str) -> list[tuple[str, tuple[int, int]]]:
    out = []
    for m in DATE_RE.finditer(text):
        y = m.group(1) or m.group(4)
        mo, d = (m.group(2), m.group(3)) if m.group(2) else (m.group(5), m.group(6))
        mo, d = int(mo), int(d)
        if 1 <= mo <= 12 and 1 <= d <= 31:
            # "21:00" is not a date; a time match covering the same span wins
            out.append(((f"{y}-" if y else "") + f"{mo:02d}-{d:02d}", m.span()))
    return out


def amounts_in_line(text: str) -> list[int]:
    t = TIME_RE.sub(" ", DATE_RE.sub(" ", text))
    return [_num(m.group(1)) for m in AMOUNT_RE.finditer(t) if 100 <= _num(m.group(1)) <= 50_000_000]


def _empty(source: str) -> dict:
    return {"payment_found": False, "merchant": None, "amount": None, "currency": None, "amount_text": None, "date": None,
            "time": None, "datetime_text": None, "card_last4": None, "status": "unknown", "status_text": None, "source": source}


def rules_current(ocr: dict) -> dict:
    """Today's rules on OCR text: largest amount >= 1000, first date and first time in reading order."""
    from .intake import regex_baseline
    from .ocr import text_of
    text = text_of(ocr)
    f = _empty("ocr+current-rules")
    b = regex_baseline(text)
    if b["amount"]:
        f.update(amount=b["amount"]["value"], currency="KRW", payment_found=True)
    d, t = dates_in(text), times_in(text)
    f["date"] = d[0][0] if d else None
    f["time"] = t[0][0] if t else None
    m = LAST4_RE.search(text)
    f["card_last4"] = m.group(1) if m else None
    f["merchant"] = "MOAHUB" if MERCHANT.search(text) else None
    return f


def rules_keyword(ocr: dict) -> dict:
    """Payment-word rules on OCR lines (see module doc). Returns fields + `lines_used` (indexes) for highlighting."""
    lines = sorted(ocr.get("lines", []), key=lambda l: (l["box"][1], l["box"][0]))
    H = float(ocr.get("height") or 1)
    f = _empty("ocr+keyword-rules")
    if not lines:
        return f
    hts = sorted(l["box"][3] - l["box"][1] for l in lines)
    med = hts[len(hts) // 2] or 1
    cy = [(l["box"][1] + l["box"][3]) / 2 for l in lines]
    merch = [i for i, l in enumerate(lines) if MERCHANT.search(l["text"])]
    status_bar = lambda i: lines[i]["box"][3] < 0.06 * H

    def near(i, j, k=2.5):
        return abs(cy[i] - cy[j]) <= k * med

    cands = []
    for i, l in enumerate(lines):
        if status_bar(i):
            continue
        for v in amounts_in_line(l["text"]):
            s = 0
            ctx = l["text"] + " " + (lines[i - 1]["text"] if i else "")
            if PAY_KW.search(ctx):
                s += 3
            if BAD_KW.search(l["text"]):
                s -= 6
            elif i and BAD_KW.search(lines[i - 1]["text"]) and not PAY_KW.search(l["text"]):
                s -= 3
            if KRW_MARK.search(l["text"]):
                s += 2
            if merch and any(near(i, j) for j in merch):
                s += 3
            if v < 1000:
                s -= 2
            h = l["box"][3] - l["box"][1]
            if h >= 1.5 * med:
                s += 1
            cands.append((s, h, -i, v, i))
    if not cands:
        return f
    s, _, _, amount, ai = max(cands)
    # amount_text is the number itself (check_fields compares its digits with the amount); the line is kept apart
    f.update(payment_found=True, amount=amount, currency="KRW", amount_text=f"{amount:,}", amount_line=lines[ai]["text"])
    anchor = cy[ai]
    tcands, dcands = [], []
    for i, l in enumerate(lines):
        if status_bar(i) or BAD_KW.search(l["text"]):
            continue
        for t, _ in times_in(l["text"]):
            tcands.append((abs(cy[i] - anchor), i, t))
        for d, _ in dates_in(re.sub(r"\d{1,2}\s*[:：]\s*\d{2}", " ", l["text"])):
            dcands.append((abs(cy[i] - anchor), i, d))
    if tcands:
        _, ti, t = min(tcands)
        f["time"] = t
        f["datetime_text"] = lines[ti]["text"]
    if dcands:
        # a list view puts the date in a section header above the row: prefer the closest date at or above the amount
        above = [c for c in dcands if cy[c[1]] <= anchor + med]
        _, _, d = min(above or dcands)
        f["date"] = d
    l4 = [(abs(cy[i] - anchor), m.group(1)) for i, l in enumerate(lines) for m in LAST4_RE.finditer(l["text"])]
    f["card_last4"] = min(l4)[1] if l4 else None
    st = []
    for i, l in enumerate(lines):
        name = next((n for n, rx in STATUS if rx.search(l["text"])), None)  # "승인 취소" is cancelled, not approved
        if name and not status_bar(i):
            st.append((abs(cy[i] - anchor), i, name, l["text"]))
    if st:
        _, _, f["status"], f["status_text"] = min(st)
    f["merchant"] = "MOAHUB" if merch else None
    f["lines_used"] = [ai]
    return f
