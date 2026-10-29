"""Investigation: read the message (Nemotron) -> run its lookup plan (scoped, read-only) -> journey -> verify chain
-> explain (Nemotron) -> citation and claim check.

LLM: NVIDIA Nemotron on Nebius Token Factory (agent/llm.py; OpenAI-compatible, key in NEBIUS_API_KEY). The older
local path (Meterless Nightshift on the seller's Mac) still works via NIGHTSHIFT_BASE_URL. Records and addresses
are masked before they leave the app. If no endpoint is configured the agent still works: the
deterministic verifier produces the verdict and a template writes the texts, and the
result is marked `llm: none` so nobody mistakes a template for a model.
"""
from __future__ import annotations
import json, os, re, time
from dataclasses import dataclass, asdict
from .chain import verify, LABELS
from .tools import Tools, OPENAI_TOOLS

SYSTEM = (
    "You are a payments investigator for a small online seller. You may only state facts that "
    "are supported by rows the tools returned, and you must cite them with the exact `ref` value in square "
    "brackets, e.g. [orders:ord_0901] or [server_logs:2026-10-13T12:00:44Z@/api/payments/confirm]. Never invent a row. "
    "Output JSON with keys: explanation (<=120 words, cite at least one ref), "
    "customer_reply (written BY the seller TO the customer, <=90 words, plain and kind; state what happened and what you will do; "
    "if nothing was charged say so clearly; never ask the customer to investigate; no internal refs; "
    "never say a fix is done or under way — the seller has not approved it yet; if the chain shows credits went to a "
    "different address, ask the customer to confirm that the address they paid with is theirs (name it) and say the credits move after they confirm; never ask them for some other address; "
    "if the message asks about an order that is not this customer's, say only that you cannot share details of other people's orders (never say it does not exist); "
    "do not greet by name or address; when you name an address, write it exactly as it appears in the rows), "
    "fix_action (one imperative sentence for the seller)."
)


@dataclass
class Trace:
    step: str
    detail: str
    ms: int


def _nightshift_key() -> str:
    """Nightshift mints its Runtime API key into a file on this Mac; read it rather than copying it around."""
    path = os.path.expanduser(os.getenv("NIGHTSHIFT_TOKEN_FILE", "~/Library/Application Support/ai.meterless.nightshift.m1m4/runtime-token"))
    try:
        return open(path).read().strip()
    except OSError:
        return ""


def _client():
    """(client, model) — Token Factory when NEBIUS_API_KEY is set (or the labelled fake with LLM_FAKE=1); else the
    older local path. Every client returned is a TracedClient, so each call is logged with model, time and tokens."""
    from .llm import token_factory_client, model_for, TracedClient, CallLog, provider_name
    if os.getenv("NEBIUS_API_KEY") or os.getenv("LLM_FAKE") == "1":
        c, _ = token_factory_client()
        return (c, model_for("explain")) if c else (None, None)
    c, m = _local_client()
    if c is None:
        return c, m
    return TracedClient(c, CallLog(), provider_name(os.getenv("NIGHTSHIFT_BASE_URL") or os.getenv("LLM_BASE_URL"))), m


def _local_client():
    base = os.getenv("NIGHTSHIFT_BASE_URL") or os.getenv("LLM_BASE_URL")
    key = os.getenv("NIGHTSHIFT_API_KEY") or (os.getenv("NIGHTSHIFT_BASE_URL") and _nightshift_key()) or os.getenv("LLM_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not base and os.getenv("OPENROUTER_API_KEY"):
        base = "https://openrouter.ai/api/v1"
    if not base:
        return None, None
    # Customer rows stay on this machine unless the operator explicitly opts in to a remote model.
    if not re.match(r"https?://(127\.0\.0\.1|localhost|\[::1\])(:\d+)?(/|$)", base) and os.getenv("ALLOW_CLOUD_LLM") != "1":
        return None, None
    # nothing listening there (e.g. Nightshift not started): answer at once with the verifier instead of waiting on retries
    import socket
    from urllib.parse import urlparse
    u = urlparse(base)
    try:
        socket.create_connection((u.hostname, u.port or (443 if u.scheme == "https" else 80)), timeout=1).close()
    except OSError:
        return None, "unreachable"
    from openai import OpenAI
    # Nightshift keeps a policy per calling app; this name is the row the operator sees and binds.
    headers = {"meterless-app": "paid-but-nothing-arrived"} if os.getenv("NIGHTSHIFT_BASE_URL") else None
    return OpenAI(base_url=base, api_key=key or "local", default_headers=headers, timeout=180), os.getenv("LLM_MODEL", "nvidia/nemotron-3.5-lightning:free")


REF_RE = re.compile(r"(?:payments|orders|grants|server_logs|mail_events):[A-Za-z0-9_./@:+-]+")


PII_FIELDS = {"email", "customer_email", "to_address", "card_last4"}


def _redact(journey: dict, customer_email: str = "") -> dict:
    """What the model sees: same rows and refs; the customer's address becomes CUSTOMER, other
    addresses keep only first letter + domain (a typo stays visible), card digits are dropped."""
    from .agent_loop import Aliaser
    al = Aliaser(customer_email)
    return {t: al.rows(rows) for t, rows in journey.items()}


def _unmask_reply(reply: str, journey: dict, customer_email: str) -> str:
    from .agent_loop import Aliaser, EMAIL_RE as _E
    al = Aliaser(customer_email)
    real = {v.lower() for rows in journey.values() for r in rows for v in r.values() if isinstance(v, str) and _E.fullmatch(v)}
    out = str(reply or "")
    for a in sorted(real, key=len, reverse=True):
        m = al.email(a)
        if m != "CUSTOMER" and m in out:
            out = out.replace(m, a)
    if customer_email:
        out = re.sub(r"(?<![A-Za-z])CUSTOMER(?![A-Za-z])", customer_email, out)
    return out


def mask_card_digits(text: str) -> str:
    """Card digits never reach the model, wherever they appear: bullet-masked numbers from the records (also
    JSON-escaped), full card numbers (13-19 digits, spaces or dashes allowed), and any 4-digit group written
    near a card word ("card ending 4242", "Visa 4242", "last four 4242", "카드 끝자리 4242")."""
    text = re.sub(r"(?:•|\\u2022){4} ?\d{4}", "•••• ****", text)
    text = re.sub(r"\b(?:\d[ -]?){12,18}\d\b", "[card number removed]", text)
    return re.sub(r"((?:card|visa|master(?:card)?|amex|debit|credit card|ending(?: in)?|last (?:four|4)(?: digits)?|카드|끝자리|끝 번호)[^\d\n]{0,20})\d{4}(?!\d)",
                  r"\1****", text, flags=re.I)


def _mask(text: str, customer_email: str) -> str:
    """Last pass over everything sent to the model: no full address survives, wherever it appears."""
    from .agent_loop import Aliaser, EMAIL_RE
    al = Aliaser(customer_email)
    text = mask_card_digits(text)
    return EMAIL_RE.sub(lambda m: al.email(m.group(0)), text)


def _citations_ok(text: str, refs: set[str]) -> tuple[bool, list[str]]:
    """Accepts [orders:ord_0901], [ref: orders:ord_0901] or a bare orders:ord_0901 — but every cited
    ref must be one the tools actually returned, and there must be at least one."""
    cited = [c.rstrip(".,;)") for c in REF_RE.findall(text)]
    bad = [c for c in cited if c not in refs]
    return (len(cited) > 0 and not bad), bad


# numbers as whole tokens: "24,900", "24 900", "₩24900" all mean 24900; "4,900" does not match 44900
# (a number may be followed by Korean units such as 원 or 개, but not be part of a code such as std30)
_FACT_NUM = re.compile(r"(?<![A-Za-z0-9_.,])\d{1,3}(?:[, ]\d{3})+(?![0-9]|[.,][0-9])|(?<![A-Za-z0-9_.,])\d{2,}(?![0-9A-Za-z_]|[.,][0-9])")
_WORD_NUM = {"ten": "10", "twenty": "20", "thirty": "30", "forty": "40", "fifty": "50", "sixty": "60", "seventy": "70",
             "eighty": "80", "ninety": "90", "hundred": "100", "열": "10", "스무": "20", "서른": "30", "마흔": "40", "쉰": "50", "예순": "60"}


def _num_tokens(values) -> set[str]:
    return {re.sub(r"[, ]", "", m) for v in values for m in re.findall(r"\d{1,3}(?:,\d{3})+|\d+", str(v))}
_FACT_DOMAIN = re.compile(r"@([\w-]+(?:\.[\w-]+)+)")    # the domain of an address (masked or not)
# state words a sentence may claim, and what the cited rows must show for each
_PAID = lambda rows: any(str(r.get("status", "")).upper() == "PAID" for r in rows if r.get("ref", "").startswith("payments:"))
_GRANTED = lambda rows: any(r.get("ref", "").startswith("grants:") and str(r.get("status", "")).lower() == "granted" for r in rows) \
    or any(re.search(r"credits? granted|granted \d+ credits", str(r.get("message", "")), re.I) for r in rows) \
    or any(r.get("ref", "").startswith("orders:") and str(r.get("credited", "")) == "1" for r in rows)
_EVENTS = lambda rows: {str(r.get("event", "")).lower() for r in rows if r.get("ref", "").startswith("mail_events:")}
# state words a sentence may claim (English and Korean), and what the cited rows must show for each. Negated forms come
# first; a sentence that states a negated form is not also read as claiming the positive one.
_STATES = [
    ("pay-", r"\b(?:payment|charge|card)\b[^.;]{0,30}\b(?:failed|declined|not completed|did not go through|cancell?ed|reversed|refunded)\b|\b(?:never charged|no charge|not charged|wasn't charged|never paid|not paid|nothing (?:was )?charged)\b|결제[가는]?\s*(?:실패|취소|되지 않|승인되지 않|거절)|승인되지\s*않|청구되지",
     # true when nothing cited is PAID, or a cited log records the failed / declined attempt itself
     lambda rows: not _PAID(rows) or any(re.search(r"fail|declin", str(r.get("message", "")), re.I) for r in rows)),
    ("pay+", r"\b(?:paid|charged|went through)\b|결제[가는]?\s*(?:완료|정상|됐|되었)",
     lambda rows: _PAID(rows) or any(str(r.get("status", "")).lower() == "paid" for r in rows if r.get("ref", "").startswith("orders:"))
                  or any("paid" in str(r.get("message", "")).lower() for r in rows)),
    ("grant-", r"\b(?:(?:never|not|n't)\s+(?:yet\s+)?(?:been\s+)?(?:granted|credited)|no credits(?: were)?(?: granted)?|credits (?:never|did not|didn't) (?:arrive|come)|credited\s*(?:=|:)?\s*0)\b|\bno\b[^.;]{0,40}\b(?:credited|granted)\b|(?:지급|적립)되지\s*않|(?:지급|적립) 안",
     lambda rows: not _GRANTED(rows)),
    ("grant+", r"(?:적립|지급)(?:됐|되었|했|돼)|\b(?:granted|credited|credits (?:are|were) (?:already )?in [\w' ]{0,25}account|received (?:the|their|your) credits)\b|지급(?:됐|되었|했)",
     lambda rows: _GRANTED(rows)),
    ("mail-", r"\b(?:never delivered|not delivered|never sent|not sent|never received|never reached|did(?: not|n't) reach|no (?:e-?mail|mail) was sent)\b|발송되지\s*않|받지 못|도착하지 않",
     lambda rows: not ({"delivered"} & _EVENTS(rows)) and (not _EVENTS(rows) or "bounced" in _EVENTS(rows) or not ({"sent"} & _EVENTS(rows)))),
    ("mail+", r"\b(?:delivered|reached the customer|arrived in|was received|received the (?:e-?mail|mail|confirmation|notice)|nothing (?:was )?wrong with the (?:e-?mail|mail))\b|(?:메일|안내)[^.]{0,10}(?:도착|정상적으로 발송|전달)",
     lambda rows: bool({"delivered", "sent"} & _EVENTS(rows)) and "bounced" not in _EVENTS(rows)),
    ("fail", r"\b(?:failed|failure|error|errored(?: out)?|blew up|crashed)\b|실패|오류",
     lambda rows: any("fail" in " ".join(str(v).lower() for v in r.values()) or "error" in str(r.get("message", "")).lower()
                      or str(r.get("http_status", "0"))[:1] in ("4", "5") or str(r.get("event", "")).lower() == "bounced" for r in rows)),
    ("bounce", r"\bbounced?\b|\b(?:rejected|returned undelivered)\b|반송|반려", lambda rows: "bounced" in _EVENTS(rows)),
    ("ok+", r"\b(?:succeeded|successful(?:ly)?|worked|went fine|returned 200|without (?:an )?error)\b|성공|정상 처리",
     lambda rows: any(str(r.get("status", "")).upper() == "PAID" for r in rows)
                  or any(str(r.get("event", "")).lower() in ("sent", "delivered") for r in rows)
                  or any(str(r.get("http_status", ""))[:1] == "2" and not re.search(r"fail|error|skip", str(r.get("message", "")), re.I) for r in rows)),
    ("paystate", r"(?<!no )\bpayment\b(?! linked| row| record)[^.;]{0,45}\b(?:pending|in progress|processing|on hold)\b|결제[가는]?\s*(?:대기|진행 중)",
     lambda rows: any(str(r.get("status", "")).upper() != "PAID" for r in rows if r.get("ref", "").startswith("payments:"))),
    ("addr=", r"\b(?:matches|same as|identical to|the same address)\b[^.;]{0,40}\b(?:payer|paid|payment)|\b(?:payer|payment)[^.;]{0,40}\b(?:matches|same address|identical)\b",
     lambda rows: len({str(r.get("email") or r.get("customer_email") or "").lower() for r in rows
                       if r.get("ref", "").startswith(("orders:", "payments:"))} - {""}) == 1),
    ("ord+", r"\border\b[^.;]{0,25}\b(?:was |is |been )?(?:confirmed|completed|fulfilled)\b|주문[이은]?\s*(?:확정|완료)",
     lambda rows: any(str(r.get("status", "")).lower() == "paid" for r in rows if r.get("ref", "").startswith("orders:"))
                  or any(re.search(r"\bconfirmed\b", str(r.get("message", "")), re.I) for r in rows)),
    ("ord-", r"\border\b[^.;]{0,25}\b(?:pending|failed|(?:not|never)\s+(?:got\s+|been\s+|yet\s+)?confirmed|unconfirmed|stuck)\b|주문[이은]?\s*(?:대기|실패|확정되지)",
     lambda rows: any(str(r.get("status", "")).lower() in ("pending", "failed") for r in rows if r.get("ref", "").startswith("orders:"))
                  or any(re.search(r"order status is (?:failed|pending)", str(r.get("message", "")), re.I) for r in rows)),
    ("twice", r"\b(?:twice|duplicate|double|two grants)\b|두 번|중복", lambda rows: sum(1 for r in rows if r.get("ref", "").startswith("grants:")) >= 2),
    ("refund", r"\brefund(?:ed)?\b|환불(?:됐|되었|했)", lambda rows: False),  # nothing in the data is a refund
]
_NEG_OF = {"pay+": "pay-", "grant+": "grant-", "mail+": "mail-", "ord+": "ord-", "ok+": "fail"}
_MONTHS = {m: f"{i:02d}" for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                                 "september", "october", "november", "december"], 1)}
_CURRENCY = re.compile(r"\b(USD|EUR|JPY|GBP|dollars?|euros?|yen)\b|\$\s*\d|달러|엔화|유로", re.I)
_TIMES = re.compile(r"\b(two|three|four|five|2|3|4|5) times\b|(두|세|네|다섯) 번", re.I)
_TIMES_N = {"two": 2, "three": 3, "four": 4, "five": 5, "두": 2, "세": 3, "네": 4, "다섯": 5}
_ROUTES = {"confirm": "confirm", "webhook": "webhook", "mail send": "mail/send", "mail-send": "mail/send", "checkout": "checkout"}
_KRW_UNIT = re.compile(r"(\d+(?:\.\d+)?)\s*(만|천)\s*원")
_IDS = re.compile(r"\b(?:ord_\d{4}|pay_[\w-]+|g_ord_[\w-]+|m_ord_[\w-]+)\b")
_CREDITS = re.compile(r"\b(\d+|ten|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred)[\s-]*(?:(?:extra|more|additional|bonus|reward)\s+)?(?:credits?|이용권|크레딧|개)", re.I)
_GRANT_COUNT = re.compile(r"\b(two|three|four|five|2|3|4|5)\s+(?:separate\s+|distinct\s+)?(?:credit\s+)?grants\b|(?:지급|적립)[이가은]?\s*(두|세|네|다섯)\s*(?:번|건)", re.I)
# a cause named in the sentence must appear in the cited rows
_CAUSES = {r"\btime(?:d)?[ -]?out\b|타임아웃|시간 초과": r"time ?out|timed out", r"\brate[ -]limit": r"rate", r"\bnetwork\b|네트워크": r"network",
           r"\bapi key\b|인증 키|api 키": r"api key", r"\bdns\b": r"dns", r"\bspam\b|스팸": r"spam", r"\bfull mailbox|mailbox (?:is )?full|메일함이 가득": r"full"}


_ISO = re.compile(r"\d{4}-\d{2}-\d{2}T(\d{2}):(\d{2}):(\d{2})")


def _row_times(row: dict) -> list[str]:
    return [str(v) for k, v in row.items() if k != "ref" and _ISO.fullmatch(str(v).rstrip("Z"))]


def _first_time(row: dict) -> str | None:
    """The moment a row records: a log's ts, an event's time, else when the row was created."""
    for k in ("ts", "at", "event_at", "occurred_at", "created_at"):
        if row.get(k) and _ISO.match(str(row[k])):
            return str(row[k])
    t = _row_times(row)
    return t[0] if t else None


def _secs(iso: str) -> float:
    import datetime as dt
    return dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


def _time_claims(low: str, refs: list[str], ref_rows: dict) -> tuple[list[str], list[str]]:
    """Times of day, the order of two cited events, and 'seconds' vs 'minutes' between them."""
    facts, missing = [], []
    rows = [ref_rows[r] for r in refs if r in ref_rows]
    stamps = [t for r in rows for t in _row_times(r)]
    for hh, mm, ss in re.findall(r"(?<![\d:])(\d{1,2}):(\d{2})(?::(\d{2}))?(?![\d:])", low):
        want = f"T{int(hh):02d}:{mm}" + (f":{ss}" if ss else "")
        facts.append(want[1:])
        if not any(want in t for t in stamps):
            missing.append(want[1:])
    timed = [(r, _first_time(ref_rows[r])) for r in refs if r in ref_rows and _first_time(ref_rows[r])]
    if len(timed) == 2:
        # which event does the sentence name first? Find each row's own words (route, mail event, table) in the text.
        def where(ref):
            words = {"payments": ["payment", "paid", "결제"], "orders": ["order", "주문"], "grants": ["grant", "credit", "지급", "적립"],
                     "mail_events": ["mail", "email", "메일"], "server_logs": []}[ref.split(":", 1)[0]]
            if ref.startswith("server_logs:"):
                route = ref.rsplit("@", 1)[-1]
                words = [w for w in re.split(r"[/_]", route) if w and w not in ("api", "admin", "payments")] or [route]
            if ref.startswith("mail_events:"):
                ev = ref.rsplit("@", 1)[-1]
                words = {"sent": ["sent", "send"], "bounced": ["bounc", "반송"], "delivered": ["deliver", "도착"]}.get(ev, [ev]) + words
            if ref.startswith("grants:") and "retry" in ref:
                words = ["retry", "재지급"] + words
            hits = [low.find(w) for w in words if low.find(w) >= 0]
            return min(hits) if hits else None
        pos = [where(r) for r, _ in timed]
        if None in pos or pos[0] == pos[1]:
            timed = []  # can't tell which event the sentence puts first: only times of day are checked
        else:
            timed = [x for _, x in sorted(zip(pos, timed))]
    if len(timed) == 2:
        (_, a), (_, b) = timed
        d = _secs(b) - _secs(a)  # the event named second minus the event named first
        claim = None
        if re.search(r"\bsame (?:second|moment|time)\b|동시에|같은 시각", low):
            claim = ("same time", abs(d) < 1)
        elif re.search(r"\b(?:before|earlier than|prior to|ahead of)\b|보다 먼저|이전에|앞서", low):
            claim = ("before", d > 0)
        elif re.search(r"\b(?:after|later than|following)\b|보다 늦게|이후에|뒤에", low):
            claim = ("after", d < 0)
        if claim:
            facts.append(claim[0])
            if not claim[1]:
                missing.append(f"{claim[0]} (cited times say otherwise)")
        if re.search(r"\b(?:\w+ )?minutes?\b|분 (?:뒤|후|만에)", low) and abs(d) < 60:
            facts.append("minutes"); missing.append("minutes (the cited rows are seconds apart)")
        if re.search(r"\bseconds?\b|초 (?:뒤|후|만에)", low) and abs(d) >= 120:
            facts.append("seconds"); missing.append("seconds (the cited rows are minutes apart)")
    return facts, missing


_STATE_TABLE = {"pay+": ("payments:",), "pay-": ("payments:",), "paystate": ("payments:",), "ord+": ("orders:",), "ord-": ("orders:",),
                "grant+": ("grants:", "orders:"), "grant-": ("grants:", "orders:"), "mail+": ("mail_events:",), "mail-": ("mail_events:",),
                "bounce": ("mail_events:",), "twice": ("grants:",)}


def _same_order(refs: list[str], ref_rows: dict) -> list[dict]:
    """Every record of the order(s) the cited rows belong to (linked by order id, payment id or grant id)."""
    keys = set()
    for r in refs:
        row = ref_rows.get(r, {})
        keys |= {str(row.get(k)) for k in ("order_id", "payment_id") if row.get(k)}
        m = re.search(r"ord_\d{4}", r)
        if m:
            keys.add(m.group(0))
    return [dict(row, ref=ref) for ref, row in ref_rows.items()
            if keys & {str(row.get("order_id")), str(row.get("payment_id"))} or any(k in ref for k in keys)]


def _claims_ok(text: str, ref_rows: dict[str, dict]) -> tuple[bool, list[dict]]:
    """Sentence by sentence, against the rows the same sentence cites (or, if it cites nothing, the rows cited
    elsewhere in the explanation): every 3+-digit number, email domain, record id (ord_/pay_/g_ord_/m_ord_) and
    "N credits" must appear there, and every payment / credit / mail state it claims (EN or KO) must match.
    Catches an explanation that cites a real row but says something the row does not show."""
    cited_all = [c.rstrip(".,;)") for c in REF_RE.findall(text)]
    report, ok = [], True
    for sent in [x.strip() for x in re.split(r"(?<=[.!?])\s+|\n+", text) if x.strip()]:
        refs = [c.rstrip(".,;)") for c in REF_RE.findall(sent)] or cited_all
        body = re.sub(r"[\u00a0\u202f\u2009]", " ", REF_RE.sub("", sent))  # models write 44\u202f900
        hay = " ".join(str(v) for r in refs for v in ref_rows.get(r, {}).values()).lower()
        low = body.lower()
        nums = _num_tokens(v for r in refs for v in ref_rows.get(r, {}).values())
        body_noids = _IDS.sub(" ", body)
        num_facts = [re.sub(r"[, ]", "", n) for n in _FACT_NUM.findall(body_noids)]
        facts = num_facts + _FACT_DOMAIN.findall(body)
        missing = [n for n in num_facts if n not in nums] + [d for d in _FACT_DOMAIN.findall(body) if d.lower() not in hay]
        tf, tm = _time_claims(low, refs, ref_rows)
        facts += tf; missing += tm
        # API paths and bare domains named in the sentence must be in the cited rows
        for path in re.findall(r"/api/[\w/.-]+", low):
            facts.append(path)
            if path.rstrip(".,") not in hay:
                missing.append(path)
        for dom in re.findall(r"(?<![@\w.])([a-z0-9-]+\.(?:com|net|org|io|kr|co\.kr))\b", low):
            facts.append(dom)
            if dom not in hay:
                missing.append(dom)
        if re.search(r"\b(?:only|just)?\s*(?:a single|one) grant\b|(?:지급|적립)[은이]?\s*한 (?:번|건)", low):
            facts.append("one grant")
            if sum(1 for r in cited_all if r.startswith("grants:")) != 1:
                missing.append("one grant")
        # dates written in Korean ("10월 14일") must be the date of a cited row
        for mo, dy in re.findall(r"(\d{1,2})월\s*(\d{1,2})일", body):
            stamp = f"-{int(mo):02d}-{int(dy):02d}"
            facts.append(f"{mo}월 {dy}일")
            if stamp not in hay:
                missing.append(f"{mo}월 {dy}일")
        # product / reward codes (std30, lite10 …) named in the sentence must be the cited rows' code
        codes = {str(r.get("reward_key", "")).lower() for r in ref_rows.values()} - {""}
        for c in codes:
            if re.search(r"(?<![a-z0-9])" + re.escape(c) + r"(?![a-z0-9])", low):
                facts.append(c)
                if c not in hay:
                    missing.append(c)
        for pat, need in _CAUSES.items():
            if re.search(pat, low):
                facts.append(re.search(pat, low).group(0))
                if not re.search(need, hay) and not re.search(need, " ".join(str(v) for r in _same_order(refs, ref_rows) for v in r.values()).lower()):
                    missing.append(re.search(pat, low).group(0))
        for a, b in _GRANT_COUNT.findall(low):
            tok = (a or b).lower(); n = _TIMES_N.get(tok) or int(tok)
            facts.append(f"{tok} grants")
            if sum(1 for r in cited_all if r.startswith("grants:")) != n:
                missing.append(f"{tok} grants")
        # amounts written with Korean units ("3만 원" = 30000)
        for q, unit in _KRW_UNIT.findall(body):
            n = str(int(float(q) * (10000 if unit == "만" else 1000)))
            facts.append(f"{q}{unit} 원")
            if n not in nums:
                missing.append(f"{q}{unit} 원")
        # a month (and day) named in the sentence must be the date of a cited row
        for mname, day in re.findall(r"\b(" + "|".join(_MONTHS) + r")\s+(\d{1,2})\b", low):  # "may" alone is a verb, not a month
            stamp = f"-{_MONTHS[mname]}-" + (f"{int(day):02d}" if day else "")
            facts.append(f"{mname} {day}".strip())
            if stamp not in hay:
                missing.append(f"{mname} {day}".strip())
        # a currency other than the cited payment's
        for m in _CURRENCY.finditer(body):
            facts.append(m.group(0))
            if not any(str(r.get("currency", "")).upper() in m.group(0).upper() for r in [dict(ref_rows[x], ref=x) for x in refs if x in ref_rows]):
                missing.append(m.group(0))
        # an endpoint named together with a cited log row must be that row's route
        logs = [ref_rows[r] for r in refs if r.startswith("server_logs:") and r in ref_rows]
        for word, route in _ROUTES.items():
            said = re.search(r"\b" + word + r"\s+(?:endpoint|step|call|route|request|handler)\b(?P<rest>[^.;]{0,25})", low)
            if said and re.search(r"never|not |n't|skipped|missing", said.group("rest")):
                continue  # "the confirm call was never executed" names an absence, not a cited row
            if logs and said and not any(route in str(l.get("route", "")) for l in logs):
                facts.append(word); missing.append(f"{word} (not the cited endpoint)")
        rows = [dict(ref_rows[r], ref=r) for r in refs if r in ref_rows]
        low = body.lower()
        # ids named in the sentence (orders, payments, grants, mails) must be in the rows it cites
        for i in _IDS.findall(body):
            facts.append(i)
            if i.lower() in hay:
                continue
            # an order named next to its own payment row: the order row (from the same journey) carries that payment_id
            o = ref_rows.get(f"orders:{i}")
            if o and any(str(ref_rows.get(r, {}).get("payment_id", "")) == str(o.get("payment_id")) for r in refs if r.startswith("payments:")):
                continue
            missing.append(i)
        # "N credits" at any digit count must match a cited grant
        for n in _CREDITS.findall(body):
            n = _WORD_NUM.get(n.lower(), n)
            facts.append(f"{n} credits")
            if not any(str(r.get("credits", "")) == n for r in rows):
                missing.append(f"{n} credits")
        hit = {name for name, pat, _ in _STATES if re.search(pat, low)}
        if re.search(r"\b(?:not|wasn't|was not|isn't|no)\s+(?:an?\s+)?[\w-]*\s*(?:failure|error)\b|실패가 아니", low):
            hit.discard("fail")  # "it was not a mail-queue failure" claims no failure
        # "N times" about grants must match the number of grant rows cited in the explanation
        for a, b in _TIMES.findall(low):
            tok = (a or b).lower()
            n = _TIMES_N.get(tok) or int(tok)
            if "grant" in low or "credit" in low or "지급" in low:
                facts.append(f"{tok} times")
                if sum(1 for r in cited_all if r.startswith("grants:")) != n:
                    missing.append(f"{tok} times")
        # a recommendation ("needs to be granted", "should re-check", "해야") states no fact about the data
        if re.search(r"\b(?:needs? to|should|must|has to|have to|will need|to be done|recommend)\b|해야|필요합니다", low):
            hit &= {"refund"}  # a promised refund is still checked
        for name, pat, holds in _STATES:
            if name not in hit or _NEG_OF.get(name) in hit:  # "never charged" is not also a claim of "charged"
                continue
            m = re.search(pat, low)
            facts.append(m.group(0))
            # "twice" is a claim about the explanation as a whole: count grants cited anywhere in it
            scope = [dict(ref_rows[r], ref=r) for r in cited_all if r in ref_rows] if name == "twice" else rows
            # if the sentence cites no row of the table this state lives in, the same order's records of that table decide
            table = _STATE_TABLE.get(name)
            if not holds(scope) and table and not any(r.startswith(table) for r in (cited_all if name == "twice" else refs)):
                scope = [r for r in _same_order(refs, ref_rows) if r["ref"].startswith(table)]
            if not holds(scope):
                missing.append(m.group(0))
        if missing:
            ok = False
        report.append({"sentence": sent, "refs": refs, "facts": facts, "unsupported": missing})
    return ok, report


def _order_belongs(tools, order_id: str, email: str) -> bool:
    # a pre-check, not part of the investigation: query directly so the logged SQL shows each lookup once
    from .tools import lit
    o = tools.db.query(f"SELECT email, payment_id FROM orders WHERE order_id = {lit('order_id', order_id)}")
    if not o:
        return False
    if str(o[0]["email"]).lower() == email.lower():
        return True
    pays = tools.db.query(f"SELECT payment_id FROM payments WHERE lower(customer_email) = lower({lit('email', email)})")
    return any(p["payment_id"] == o[0].get("payment_id") for p in pays)


def investigate(message: str, email: str = "", order_id: str = "", backend=None, use_model: bool = True, lang: str = "",
                first_address_rule: bool = False) -> dict:
    """first_address_rule=True reproduces the old regex baseline (first address in the message is the sender); it is
    used only to measure and to show "what the rules alone would have found" to the seller. Otherwise a message with
    several customer addresses and no sender named by the reader reads nobody's records."""
    from .sql_backend import get_backend
    db = backend or get_backend()
    tools, trace, t0 = Tools(db), [], time.time()
    # reply language: what the page asks for (the seller's language toggle), else the language of the message
    # reply language: a Korean message gets a Korean reply; otherwise the page's language toggle decides
    lang = "ja" if re.search(r"[\u3040-\u30ff]", message or "") else "ko" if re.search(r"[가-힣]", message or "") else (lang if lang in ("en", "ko") else "en")

    def mark(step, detail):
        trace.append(Trace(step, detail, int((time.time() - t0) * 1000)))

    # 1. locate the order (email or order id; fall back to an id mentioned in the message)
    email_given, order_given = bool(email), bool(order_id)
    if order_id and not re.fullmatch(r"ord_\d{4}", order_id): order_id = ""
    if email and not re.fullmatch(r"[\w.+-]+@[\w-]+(\.[\w-]+)+", email): email = ""
    if not order_id:
        m = re.search(r"ord_\d{4}", message or ""); order_id = m.group(0) if m else ""
    if not email:  # the first address in the message that is not one of the shop's own
        from .intake import body_addresses
        candidates = body_addresses(message)
        email = candidates[0] if candidates else ""
    client, model = _client() if use_model else (None, None)
    unreachable = client is None and model == "unreachable"
    calls = getattr(client, "log", None)
    if calls is not None:
        del calls[:]  # this investigation's calls only
    # 0. with a model: Nemotron reads the message (sender among several addresses, claims, foreign order numbers)
    #    and plans the lookups. Everything it returns is grounded against the message by code (agent/intake.py).
    intake, foreign = None, []
    if client and os.getenv("INTAKE", "1") != "0":
        from .intake import read_with_routing
        intake = read_with_routing(client, message or "")
        mark("intake", "read the message" if intake.get("ok") else f"failed: {intake.get('error', '')}"[:120])
        g = intake.get("grounded") if intake.get("ok") else None
        if g:
            if g.get("sender_email") and not email_given:
                email = g["sender_email"]
            elif not email_given and email and len(candidates) > 1:
                # the reader named no sender and the message has several addresses: do not guess whose records to read
                mark("sender_scope", "no sender identified among several addresses — nobody's records were read")
                email = ""

            foreign = g.get("foreign_order_ids") or []
            own = [o for o in g.get("order_ids", []) if o not in foreign]
            if not order_given:
                order_id = own[0] if own else (order_id if order_id not in foreign else "")
    if not email_given and not first_address_rule and email and len(candidates) > 1 and not (
            intake and intake.get("ok") and (intake.get("grounded") or {}).get("sender_email")):
        # no model reading (no key, past the live limit, failed call): never guess among several addresses
        mark("sender_scope", "several addresses and no reader to tell them apart — nobody's records were read")
        email = ""
    if not order_id and not email:
        return {"ok": False, "headline": "Add the order number (ord_0000) or the customer's email to the message.", "trace": [asdict(t) for t in trace],
                "backend": db.name, "intake": _public_intake(intake), "model_calls": list(calls or []), "llm": "none"}
    # The sender's address decides whose records may be read. An order number written in the message is only
    # used if it belongs to that sender (order address or payer address); otherwise it is ignored and said so.
    ignored_order = ""
    if email and order_id and not _order_belongs(tools, order_id, email):
        ignored_order, order_id = order_id, ""
        mark("sender_scope", f"{ignored_order} is not this sender's order — ignored")
    if not ignored_order and foreign:
        ignored_order = foreign[0]
        mark("sender_scope", f"{ignored_order} was asked for on someone else's behalf — not read")
    sender_unverified = bool(order_id and not email)
    steps, loop_finding = [], ""
    target = None
    # 1. the model's plan, run through the sender-scoped read-only tools
    if intake and intake.get("ok") and email and intake["grounded"].get("plan"):
        from .agent_loop import Scope
        from .intake import execute_plan
        scope = Scope(email, tools, seed_order=order_id or "")
        ex = execute_plan(intake["grounded"]["plan"], scope, tools, intake.get("mapping", {}))
        steps = ex["steps"]
        mark("plan", f"{len(steps)} planned lookup(s), reached {ex['journey_order'] or 'no order'}")
        if ex["journey_order"]:
            target = tools.find_orders(order_id=ex["journey_order"])[0]
        elif ex["orders"]:  # the plan found the sender's orders but its last step was refused or missing: code picks
            from .intake import best_order
            target = tools.find_orders(order_id=best_order(ex["orders"]))[0]
            mark("plan", f"plan stopped early; picked {target['order_id']} from the orders it found")
    # 1a. no plan result: the model decides lookups turn by turn (tools are read-only and scoped to the
    #     sender's own trail; ids are validated). If the seller pasted an order id, the sender is that order's address.
    if target is None and client and (email or order_id) and os.getenv("AGENT_LOOP", "1") != "0":
        try:
            from .agent_loop import investigate_loop
            seed = ""
            if order_id and not email:
                o0 = tools.find_orders(order_id=order_id)
                email, seed = (o0[0]["email"], order_id) if o0 else ("", "")
            elif order_id:
                seed = order_id
            if email:
                res = investigate_loop(client, model_loop(model), message, email, tools, seed_order=seed)
                steps, loop_finding = steps + res["steps"], res["finding"]
                mark("agent_loop", f"{len(res['steps'])} step(s), named {res['order_id'] or 'nothing'}")
                if res["ok"]:
                    target = tools.find_orders(order_id=res["order_id"])[0]
        except Exception as e:
            mark("agent_loop", f"failed: {type(e).__name__}"[:120])
    # 1b. without a model (or if it found nothing): our own lookup, then the PSP ledger by payer address
    if target is None:
        orders = tools.find_orders(email=email, order_id=order_id)
        mark("find_orders", f"{len(orders)} order(s) for {order_id or email}")
        if not orders and email:
            pays = tools.find_payments(email)
            mark("find_payments", f"{len(pays)} payment-provider payment(s) by this address")
            for p in pays:
                orders += tools.order_for_payment(p["payment_id"])
            mark("order_for_payment", f"{len(orders)} order(s) behind those payments")
        if not orders:
            return {"ok": False, "headline": f"No order or payment found for {order_id or email}. Check the address the customer paid with, or ask for the order number.",
                    "trace": [asdict(t) for t in trace], "steps": steps, "backend": db.name,
                    "intake": _public_intake(intake), "model_calls": list(calls or []), "llm": model or "none"}
        # if several orders, investigate the most recent one that is not plainly healthy first
        target = next((o for o in orders if not (o["status"] == "paid" and o["credited"] == "1")), orders[0])

    # 2. journey + 3. deterministic verification (the part that is never delegated to a model)
    journey = tools.order_journey(target["order_id"]); mark("order_journey", f"one query; {tools.sql_log[-1]['rows'] if tools.sql_log else '?'} joined rows → {sum(len(v) for v in journey.values())} rows across {sum(1 for v in journey.values() if v)} tables")
    verdict = verify(journey); mark("verify_chain", f"broken={verdict.broken}")
    refs = {r["ref"] for rows in journey.values() for r in rows}

    # 4. explanation + reply + fix (LLM, citation-checked)
    texts, llm_used, citation = None, ("verifier-only" if not use_model else "unreachable" if unreachable else "none"), {"checked": False}
    receipts = [st.get("receipt") for st in steps]
    if client:
        try:
            lang_note = {"ko": " Reply language: Korean (polite 존댓말).", "ja": " Reply language: Japanese (polite です/ます)."}.get(lang, "")
            user_payload = _mask(json.dumps(ensure_ascii=False, obj={"customer_message": message[:2000], "chain": verdict.to_dict(),
                                             "rows": _redact(journey, email), "investigation": loop_finding}, default=str), email)
            from .agent_loop import _parse
            for attempt in (1, 2):  # the hosted endpoint sometimes times out or returns no JSON; one retry
                try:
                    resp = client.chat.completions.create(**({"_role": "explain"} if hasattr(client, "log") else {}), model=model, temperature=0.2, max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4000")), reasoning_effort=os.getenv("LLM_REASONING", "none"),
                        messages=[{"role": "system", "content": SYSTEM + lang_note},
                                  {"role": "user", "content": user_payload}])
                    texts = _parse(resp.choices[0].message.content or "")
                    if not texts:
                        raise ValueError("model returned no JSON object")
                    break
                except Exception as e:
                    texts = None
                    if attempt == 2:
                        raise
                    mark("llm_explain_retry", f"{type(e).__name__}"[:80])
            llm_used = getattr(resp, "model", None) or model
            from .agent_loop import meterless_receipt
            receipts.append(meterless_receipt(resp))
            texts["_raw_explanation"] = texts.get("explanation", "")
            ok, bad = _citations_ok(texts.get("explanation", ""), refs)
            ref_rows = {r["ref"]: r for rows in journey.values() for r in rows}
            claims_ok, claims = _claims_ok(texts.get("explanation", ""), ref_rows)
            citation = {"checked": True, "ok": ok and claims_ok, "unknown_refs": bad, "claims": claims,
                        "claims_ok": claims_ok}
            ok = ok and claims_ok
            texts["fix_action"] = verdict.suggested_fix  # the fix is decided by the verifier, never by the model
            # The model saw CUSTOMER and masked forms (l***@domain); put the real addresses of this case's own rows back
            # before the reply reaches the seller. Only addresses from the sender's own trail can appear here.
            texts["customer_reply"] = _unmask_reply(texts.get("customer_reply", ""), journey, email)
            why_not = _reply_problem(texts.get("customer_reply", ""), verdict)
            if why_not:
                print(f"[investigator] model reply not used ({why_not}): {texts.get('customer_reply', '')[:300]!r}", flush=True)
                texts["customer_reply"] = _template_reply(verdict, lang)
                citation["reply_replaced"] = True; citation["reply_reason"] = why_not
            if ok and re.search(r"refund|compensat|discount|voucher|환불|보상|할인", texts.get("explanation", ""), re.I):
                ok = False  # money is a person's decision; a steered explanation falls back to the verifier's text
            if not ok:
                texts["explanation"] = verdict.root_cause + " " + " ".join(f"[{r}]" for r in dict.fromkeys(r for l in verdict.links if l.state == "red" for r in l.refs))
                citation["replaced_with_verifier_text"] = True
            mark("llm_explain", f"{model} citations_ok={ok}")
        except Exception as e:  # keep the demo honest: show that the model step failed
            mark("llm_explain", f"failed: {type(e).__name__}: {e}"[:200])
            print(f"[investigator] explain call failed: {type(e).__name__}: {str(e)[:400]}", flush=True)
            # nothing listening at the configured address (e.g. Nightshift not running) is not a model failure
            llm_used = "unreachable" if "Connection" in type(e).__name__ else "failed"
    if texts is None:
        texts = {"explanation": verdict.root_cause + " " + " ".join(f"[{r}]" for r in dict.fromkeys(r for l in verdict.links if l.state == "red" for r in l.refs)),
                 "customer_reply": _template_reply(verdict, lang), "fix_action": verdict.suggested_fix}
        mark("template_texts", {"failed": "model call failed — verifier text used", "unreachable": "no model reachable — verifier text used", "verifier-only": "re-check after a fix — verifier only"}.get(llm_used, "no LLM endpoint configured — verifier text used"))

    rules_only = None
    if intake and intake.get("ok"):
        # what the agent would have found without the model reading the message (no model call; same data)
        ro = investigate(message, email if email_given else "", order_id if order_given else "", backend=db, use_model=False,
                         first_address_rule=True)
        rules_only = {"ok": ro.get("ok"), "order_id": ro.get("order_id"), "broken": ro.get("broken"), "headline": ro.get("headline"),
                      "same": ro.get("order_id") == target["order_id"] and ro.get("broken") == verdict.broken}
    from .compare import compare_claims
    claims_vs = compare_claims(intake["grounded"] if intake and intake.get("ok") else None, journey, verdict)
    return {"ok": True, "order_id": target["order_id"], "email": target["email"], "headline": verdict.headline,
            "intake": _public_intake(intake), "claims_vs_records": claims_vs, "rules_only": rules_only,
            "model_calls": list(calls or []), "provider": getattr(client, "provider", None),
            "ignored_order": ignored_order, "sender_unverified": sender_unverified,
            "chain": [{"name": l.name, "label": LABELS[l.name], "state": l.state, "note": l.note, "refs": l.refs} for l in verdict.links],
            "broken": verdict.broken, "verified": verdict.verified, "unverified": verdict.unverified,
            "explanation": texts["explanation"], "customer_reply": texts["customer_reply"], "fix_action": texts["fix_action"],
            "rows": journey, "trace": [asdict(t) for t in trace], "steps": steps, "queries": tools.sql_log, "receipts": [r for r in receipts if r], "llm": llm_used, "citation_check": citation, "backend": db.name,
            "lang": lang, "elapsed_ms": int((time.time() - t0) * 1000)}


def model_loop(default: str) -> str:
    from .llm import model_for
    return os.getenv("LLM_MODEL_LOOP") or (model_for("loop") if os.getenv("NEBIUS_API_KEY") else default)


def _public_intake(intake: dict | None) -> dict | None:
    """What the page shows about the intake step. Real addresses are never included: placeholders and masked forms only."""
    if not intake:
        return None
    out = {k: intake.get(k) for k in ("ok", "masked", "placeholders", "model", "error", "routing")}
    g = intake.get("grounded")
    if g:
        out["grounded"] = {k: v for k, v in g.items() if k != "sender_email"}
    return out


REPLY_MUST = {None: r"never charged|not charged|nothing was charged|no payment was (?:taken|made)|no charge|wasn't charged|was not charged|not been charged|in your account|went through|청구되지|이용권|請求|クレジット",
              "order_created": r"payment (went|came) through|was processed|successful|succeeded|confirm|releas|grant|결제|확인|이용권|決済|お支払い|確認|クレジット",
              "credit_granted": r"twice|duplicate|double|two|두 번|중복|二重|重複", "mail_delivered": r"mail|notice|notif|메일|안내|メール",
              "account_mismatch": r"address|account|email|typo|주소|アドレス|アカウント"}


def _reply_ok(reply: str, v) -> bool:
    return _reply_problem(reply, v) is None


def _reply_problem(reply: str, v) -> str | None:
    """Why the model's reply can't be sent (None if it can). The reply must be the seller speaking and must carry
    the verdict; otherwise the template is safer."""
    if not reply:
        return "empty"
    if re.search(r"\b(let me check my account|you gave me|my order|my credits)\b", reply, re.I):
        return "written as the customer"
    # "feel free to reply" is fine; "for free" / "a free month" is a promise of money
    if re.search(r"refund|compensat|discount|voucher|\bfor free\b|free of charge|\bfree (?:credits?|month|pack|plan|book)|환불|보상|할인|무료|返金|補償|割引|無料", reply, re.I):
        return "promises money"
    if v.broken == "account_mismatch" and (not re.search(r"confirm|확인해|ご確認", reply, re.I)
                                           or re.search(r"(are|am|we're|i'm) (now )?moving|right away|already moved|옮기고 있|옮겼", reply, re.I)):
        return "moves credits before the customer confirms"  # credits move only after confirmation and approval
    if re.search(r"\*\*\*@|(?<![A-Za-z])CUSTOMER(?![A-Za-z])|(?<![A-Za-z])EMAIL_\d", reply):  # also "CUSTOMER님", "CUSTOMERさま"
        return "contains a masked placeholder"  # placeholders are for the model, never for the customer
    if re.search(r"where you('d| would) like|which (email|address)|(send|give|tell) (us|me) (the|your|an?) (new |other |different )?(email|address)|another (email|address)|new (email|address)|원하시는 (주소|이메일)|다른 (주소|이메일)을 알려", reply, re.I):
        return "asks for a different address"  # the fix only moves credits to the payer's own address
    key = v.broken if v.broken in REPLY_MUST else None
    if key is None and "never charged" not in v.headline.lower() and v.broken is None:
        must = r"in your account|went through|everything|이용권|계정|クレジット|アカウント"
    else:
        must = REPLY_MUST[key]
    return None if re.search(must, reply, re.I) else "does not state the finding"


def _template_reply(v, lang: str = "en") -> str:
    if lang == "ko":
        return _template_reply_ko(v)
    if lang == "ja":
        return _template_reply_ja(v)
    if v.broken is None and "never charged" in v.headline.lower():
        return "Thank you for writing. I checked our payment provider: no charge was made on your card for this order, so nothing is missing and nothing will be billed. I can send you a fresh checkout link whenever you are ready."
    if v.broken == "order_created":
        return "Thank you for your patience. I can confirm your payment went through on our provider's side. Our system did not complete your order after that — that is our fault, not yours. I will release your credits as soon as this is fixed on our side, and you will get a confirmation email."
    if v.broken == "credit_granted":
        return "Thank you for writing. Your payment and order are fine. I found that the credits were issued twice by mistake; I will keep your purchased credits in place and correct the duplicate on our side. Nothing further is needed from you."
    if v.broken == "account_mismatch":
        return "Thank you for writing, and sorry for the worry. Your payment went through. The order was saved under a slightly different email address than the one you paid with, so the credits and the confirmation went there instead. Could you confirm that the address you paid with is yours? As soon as you do, I will move the credits there."
    if v.broken == "mail_delivered":
        return "Thank you for your patience. Your credits are already in your account — our confirmation email failed to send, so you were never told. Please log in and check your balance; I will resend the confirmation as well."
    return "Thank you for writing. I checked every step of your order and everything went through; your credits are in your account."


def _template_reply_ko(v) -> str:
    """Same facts as the English templates; polite 존댓말; no internal refs."""
    if v.broken is None and "never charged" in v.headline.lower():
        return "문의해 주셔서 감사합니다. 결제 대행사를 확인한 결과 이번 주문에 대해 카드에 청구된 내역이 없습니다. 빠진 이용권도 없고 추가 청구도 되지 않습니다. 원하시면 새 결제 링크를 보내 드리겠습니다."
    if v.broken == "order_created":
        return "기다려 주셔서 감사합니다. 결제 대행사 기준으로는 결제가 정상 완료된 것을 확인했습니다. 이후 주문을 마무리하지 못한 것은 저희 쪽 문제입니다. 저희 쪽에서 바로잡는 대로 이용권을 지급하고 확인 메일을 보내 드리겠습니다."
    if v.broken == "credit_granted":
        return "문의해 주셔서 감사합니다. 결제와 주문은 정상입니다. 이용권이 실수로 두 번 지급된 것을 확인했고, 구매하신 이용권은 그대로 두고 중복분만 정리하겠습니다. 고객님께서 추가로 하실 일은 없습니다."
    if v.broken == "account_mismatch":
        return "문의해 주셔서 감사하고, 걱정 끼쳐 드려 죄송합니다. 결제는 정상입니다. 주문은 결제하신 주소와 조금 다른 이메일로 저장되어 이용권과 안내 메일이 그쪽으로 갔습니다. 이 주소가 맞으신지 확인해 주시면, 바로 고객님 계정으로 이용권을 옮겨 드리겠습니다."
    if v.broken == "mail_delivered":
        return "기다려 주셔서 감사합니다. 이용권은 이미 계정에 지급되어 있습니다. 확인 메일 발송에 실패해 안내를 드리지 못했습니다. 로그인하셔서 잔액을 확인해 주세요. 확인 메일을 다시 보내 드리겠습니다."
    return "문의해 주셔서 감사합니다. 주문 전 단계를 확인했고 모두 정상입니다. 이용권은 계정에 있습니다."


def _template_reply_ja(v) -> str:
    """Same facts as the English templates, polite Japanese; no internal refs."""
    if v.broken is None and "never charged" in v.headline.lower():
        return "お問い合わせありがとうございます。決済代行会社の記録を確認しましたが、このご注文についてカードへの請求はございません。不足しているクレジットも追加の請求もございません。ご希望でしたら新しいお支払いリンクをお送りします。"
    if v.broken == "order_created":
        return "お待たせして申し訳ございません。決済代行会社の記録では、お支払いは正常に完了しております。その後のご注文処理が完了しなかったのは当店側の問題です。修正が済み次第、クレジットを付与し、確認メールをお送りします。"
    if v.broken == "credit_granted":
        return "お問い合わせありがとうございます。お支払いとご注文は正常です。クレジットが誤って二重に付与されていたことを確認しました。ご購入分はそのままにし、重複分のみ当店側で整理いたします。お客様のお手続きは不要です。"
    if v.broken == "account_mismatch":
        return "お問い合わせありがとうございます。ご心配をおかけして申し訳ございません。お支払いは正常に完了しています。ご注文がお支払いのメールアドレスとわずかに異なるアドレスで保存されたため、クレジットと案内メールがそちらに届いていました。お支払いに使われたアドレスがお客様のものかご確認いただければ、すぐにクレジットを移します。"
    if v.broken == "mail_delivered":
        return "お待たせして申し訳ございません。クレジットはすでにアカウントに付与されています。確認メールの送信に失敗したため、お知らせできておりませんでした。ログインして残高をご確認ください。確認メールも再送いたします。"
    return "お問い合わせありがとうございます。ご注文のすべての段階を確認しましたが、すべて正常に完了しており、クレジットはアカウントにございます。"
