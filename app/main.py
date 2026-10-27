"""FastAPI app: one page, one question — "I paid, but nothing arrived." — one chain.

Two ways to run it:
  local (default)   the seller's own machine; one shared data set; the model is whatever .env.local configures.
  DEMO_PUBLIC=1     safe to put on the internet for judges:
                    - every visitor gets a private copy of the synthetic data (made on their first Approve, gone after
                      DEMO_SANDBOX_TTL seconds idle); nobody can change what another visitor sees,
                    - the six example cases answer instantly from a recorded Token Factory run (data/precomputed/),
                      with a "Run it live" button,
                    - live model runs are rate-limited per visitor and per day; past the limit the verifier still
                      answers (no model) and the page says so,
                    - the Token Factory key stays on the server; the agent loop is off so a live run is two model calls.
"""
from __future__ import annotations
import json, os, secrets, threading, time
from collections import OrderedDict, deque
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env.local")
PUBLIC = os.getenv("DEMO_PUBLIC") == "1"
if PUBLIC:
    if os.getenv("LLM_FAKE") == "1":
        raise SystemExit("DEMO_PUBLIC=1 refuses LLM_FAKE=1: judges must never see scripted text as a model's.")
    for k in ("ZETARIS_JDBC_URL", "ZETARIS_JDBC_JAR", "ZETARIS_SQL_URL", "ZETARIS_API_KEY", "NIGHTSHIFT_BASE_URL", "OPENROUTER_API_KEY"):
        os.environ.pop(k, None)  # public demo: synthetic CSVs + Token Factory only
    os.environ.setdefault("AGENT_LOOP", "0")
    os.environ.setdefault("LLM_TIMEOUT", "45")

from agent.actions import READONLY_MSG, NeedsCustomerConfirmation, NothingToFix, ReadOnlyBackend, approve  # noqa: E402
from agent.investigator import investigate  # noqa: E402
from agent.llm import TOKEN_FACTORY_URL, model_for, provider_name  # noqa: E402

app = FastAPI(title="Paid, but nothing arrived", docs_url=None if PUBLIC else "/docs", redoc_url=None, openapi_url=None if PUBLIC else "/openapi.json")
ROOT = Path(__file__).resolve().parent
CASES = ROOT.parent / "data" / "out" / "cases.json"
PRECOMPUTED = ROOT.parent / "data" / "precomputed"
COOKIE = "pbna_sid"


class Ask(BaseModel):
    message: str = Field(max_length=2000)
    email: str = Field(default="", max_length=200)
    order_id: str = Field(default="", max_length=20)
    lang: str = Field(default="", max_length=4)
    case: int | None = None          # an example button: may be answered from the recorded run
    live: bool = False                # "Run it live" on an example


class ProofAsk(BaseModel):
    image: str = Field(default="", max_length=12_000_000)   # data URL or bare base64 of the photo (paste or upload)
    message: str = Field(default="", max_length=2000)
    email: str = Field(default="", max_length=200)
    lang: str = Field(default="", max_length=4)
    example: str = Field(default="", max_length=40)          # one of the example photos (may be answered from a recorded run)
    live: bool = False


class ApproveBody(BaseModel):
    order_id: str = Field(max_length=20)
    approved_by: str = Field(default="seller", max_length=40)
    customer_confirmed: bool = False


# ---------------- per-visitor data (public mode) ----------------

class Sandboxes:
    """Visitor id -> their own DuckDB copy of the synthetic data. Made only when a visitor first writes (Approve);
    until then they read the shared copy, which is never written in public mode. About 12 MB and 25 ms each."""

    def __init__(self, cap: int, ttl: int):
        self.cap, self.ttl = cap, ttl
        self._d: OrderedDict[str, tuple[object, float]] = OrderedDict()
        self._lock = threading.Lock()
        self._shared = None

    def shared(self):
        from agent.sql_backend import DuckDBBackend
        with self._lock:
            if self._shared is None:
                self._shared = DuckDBBackend()
            return self._shared

    def get(self, sid: str, create: bool = False):
        from agent.sql_backend import DuckDBBackend
        now = time.time()
        with self._lock:
            for k in [k for k, (_, t) in self._d.items() if now - t > self.ttl]:
                del self._d[k]
            if sid in self._d:
                db, _ = self._d.pop(sid)
                self._d[sid] = (db, now)
                return db
            if not create:
                return None
            while len(self._d) >= self.cap:
                self._d.popitem(last=False)  # the visitor idle the longest loses their changes
            db = DuckDBBackend()
            self._d[sid] = (db, now)
            return db

    def drop(self, sid: str):
        with self._lock:
            self._d.pop(sid, None)


SANDBOXES = Sandboxes(cap=int(os.getenv("DEMO_SANDBOX_CAP", "30")), ttl=int(os.getenv("DEMO_SANDBOX_TTL", "1800")))


class Limiter:
    """Live model runs: per visitor address per hour, and per day for the whole demo (protects the credits)."""

    def __init__(self, per_ip_hour: int, per_day: int, concurrent: int):
        self.per_ip_hour, self.per_day = per_ip_hour, per_day
        self.ip: dict[str, deque] = {}
        self.day: deque = deque()
        self.lock = threading.Lock()
        self.slots = threading.BoundedSemaphore(concurrent)

    def allow(self, ip: str) -> str | None:
        now = time.time()
        with self.lock:
            while self.day and now - self.day[0] > 86400:
                self.day.popleft()
            q = self.ip.setdefault(ip, deque())
            while q and now - q[0] > 3600:
                q.popleft()
            if len(self.ip) > 5000:  # forget idle visitors
                for k in [k for k, v in self.ip.items() if not v]:
                    del self.ip[k]
            if len(self.day) >= self.per_day:
                return "the demo's daily limit of live model runs is used up"
            if len(q) >= self.per_ip_hour:
                return f"you have used {self.per_ip_hour} live model runs this hour"
            q.append(now); self.day.append(now)
            return None


LIMITER = Limiter(int(os.getenv("DEMO_LIVE_PER_IP_HOUR", "8")), int(os.getenv("DEMO_LIVE_PER_DAY", "300")), int(os.getenv("DEMO_LIVE_CONCURRENT", "3")))


def _sid(request: Request) -> str:
    sid = request.cookies.get(COOKIE, "")
    sid = sid if (len(sid) == 32 and sid.isalnum()) else secrets.token_hex(16)
    request.state.https = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
    return sid


def _out(resp, sid: str, request: Request | None = None):
    https = bool(request is not None and getattr(request.state, "https", False))
    resp.set_cookie(COOKIE, sid, max_age=7 * 86400, httponly=True, samesite="lax", secure=https)
    return resp


def _ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return (fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "?"))[:64]


def _backend(sid: str):
    if not PUBLIC:
        return None  # local mode: the process-wide backend (agent.sql_backend.get_backend)
    return SANDBOXES.get(sid) or SANDBOXES.shared()


def _recorded(case: int | None, sid: str):
    """The recorded Token Factory run for an example case — only while this visitor has not changed their data."""
    if case is None or not PUBLIC or SANDBOXES.get(sid) is not None:
        return None
    p = PRECOMPUTED / f"case{int(case)}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text())


# ---------------- routes ----------------

@app.get("/", response_class=HTMLResponse)
def index():
    return (ROOT / "index.html").read_text()


EXAMPLES = ROOT / "proof_examples"


def _examples() -> list[dict]:
    f = EXAMPLES / "examples.json"
    return json.loads(f.read_text()) if f.exists() else []


@app.get("/api/proof/examples")
def proof_examples():
    return [{k: e.get(k) for k in ("id", "label", "label_ko", "lang", "message")} for e in _examples()]


@app.get("/proof-examples/{name}")
def proof_example_image(name: str):
    e = next((x for x in _examples() if f"{x['id']}.jpg" == name), None)
    if not e:
        return PlainTextResponse("not found", status_code=404)
    return FileResponse(EXAMPLES / f"{e['id']}.jpg", media_type="image/jpeg")


@app.post("/api/proof")
def api_proof(ask: ProofAsk, request: Request):
    """A customer's payment screenshot: the vision model reads it, the ledger decides. The photo is not stored."""
    import base64, binascii
    from agent.proof import investigate_proof
    sid = _sid(request)
    ex = next((x for x in _examples() if x["id"] == ask.example), None) if ask.example else None
    message = ask.message or (ex or {}).get("message", "")
    if ex and not ask.live and PUBLIC and SANDBOXES.get(sid) is None:
        rec = PRECOMPUTED / f"proof_{ex['id']}.json"
        if rec.exists():
            d = json.loads(rec.read_text())
            return _out(JSONResponse({**d["result"], "recorded": d["meta"]}), sid, request)
    if ex:
        data = (EXAMPLES / f"{ex['id']}.jpg").read_bytes()
    else:
        raw = ask.image.split(",", 1)[1] if ask.image.startswith("data:") else ask.image
        try:
            data = base64.b64decode(raw, validate=True)
        except (binascii.Error, ValueError):
            return PlainTextResponse("The image could not be decoded.", status_code=400)
    use_model, limited = True, None
    if PUBLIC:
        limited = LIMITER.allow(_ip(request))
        if limited:
            use_model = False
        elif not LIMITER.slots.acquire(timeout=20):
            use_model, limited = False, "too many live runs at this moment"
    try:
        r = investigate_proof(data, message, ask.email, backend=_backend(sid), use_model=use_model, lang=ask.lang)
    finally:
        if PUBLIC and use_model:
            LIMITER.slots.release()
    if limited:
        r["limited"] = limited
        r["llm"] = "limited"
    return _out(JSONResponse(r), sid, request)


@app.get("/api/config")
def config():
    has_key = bool(os.getenv("NEBIUS_API_KEY"))
    recorded = sorted(int(p.stem[4:]) for p in PRECOMPUTED.glob("case*.json")) if PRECOMPUTED.exists() else []
    return {"public": PUBLIC, "provider": provider_name(os.getenv("LLM_BASE_URL") or (TOKEN_FACTORY_URL if has_key else None)),
            "model_intake": model_for("intake"), "model_explain": model_for("explain"),
            "models": {r: model_for(r) for r in ("vision", "intake", "escalate", "explain", "reply")},
            "live_model": has_key or os.getenv("LLM_FAKE") == "1", "fake": os.getenv("LLM_FAKE") == "1",
            "recorded_cases": recorded,
            "limits": {"per_hour": LIMITER.per_ip_hour, "sandbox_minutes": SANDBOXES.ttl // 60} if PUBLIC else None}


@app.get("/api/cases")
def cases():
    return json.loads(CASES.read_text()) if CASES.exists() else []


@app.post("/api/investigate")
def api_investigate(ask: Ask, request: Request):
    sid = _sid(request)
    if not ask.live:
        rec = _recorded(ask.case, sid)
        if rec:
            return _out(JSONResponse({**rec["result"], "recorded": rec["meta"]}), sid, request)
    use_model, limited = True, None
    if PUBLIC:
        limited = LIMITER.allow(_ip(request))
        if limited:
            use_model = False
        elif not LIMITER.slots.acquire(timeout=20):
            use_model, limited = False, "too many live runs at this moment"
    try:
        r = investigate(ask.message, ask.email, ask.order_id, backend=_backend(sid), lang=ask.lang, use_model=use_model)
    finally:
        if PUBLIC and use_model:
            LIMITER.slots.release()
    if limited:
        r["limited"] = limited
        r["llm"] = "limited"
    return _out(JSONResponse(r), sid, request)


@app.post("/api/approve")
def api_approve(body: ApproveBody, request: Request):
    """Apply a human-approved fix (DuckDB demo data only). In public mode it changes only this visitor's copy."""
    sid = _sid(request)
    db = SANDBOXES.get(sid, create=True) if PUBLIC else None
    try:
        return _out(JSONResponse(approve(body.order_id, body.approved_by, backend=db, customer_confirmed=body.customer_confirmed)), sid, request)
    except NeedsCustomerConfirmation as e:
        return _out(PlainTextResponse(str(e), status_code=409), sid, request)
    except ReadOnlyBackend:
        return PlainTextResponse(READONLY_MSG, status_code=409)
    except NothingToFix:
        return PlainTextResponse("Nothing to fix", status_code=400)
    except ValueError as e:
        return PlainTextResponse(str(e), status_code=400)


@app.get("/api/audit")
def api_audit(request: Request):
    """Every approved fix, newest first (demo data; in public mode, this visitor's fixes only)."""
    from agent.sql_backend import get_backend
    sid = _sid(request)
    db = SANDBOXES.get(sid) if PUBLIC else get_backend()
    if db is None:
        return _out(JSONResponse({"backend": "duckdb-local", "actions": []}), sid, request)
    if "duckdb" not in db.name:
        return JSONResponse({"backend": db.name, "actions": [], "note": "read-only backend: no fixes are applied here"})
    with db.lock:
        rows = db.query("SELECT * FROM actions ORDER BY ts DESC")
    return _out(JSONResponse({"backend": db.name, "actions": rows}), sid, request)


@app.post("/api/reset")
def api_reset(request: Request):
    """Put the demo bugs back (public mode: this visitor's copy only)."""
    from agent.sql_backend import _CACHE, get_backend
    if PUBLIC:
        sid = _sid(request)
        SANDBOXES.drop(sid)
        return _out(JSONResponse({"ok": True, "backend": "duckdb-local"}), sid, request)
    if "duckdb" not in get_backend().name:
        return PlainTextResponse("Reset is only for the offline demo.", status_code=409)
    _CACHE.clear()
    return JSONResponse({"ok": True, "backend": get_backend().name})


@app.post("/api/evidence")
def evidence(ask: Ask, request: Request):
    """Dispute-ready evidence bundle: the chain, every cited raw row, what was and was not verified.
    Built by the verifier alone (no model call), so it is instant and costs nothing."""
    sid = _sid(request)
    r = investigate(ask.message, ask.email, ask.order_id, backend=_backend(sid), use_model=False)
    if not r.get("ok"):
        return PlainTextResponse(r["headline"])
    lines = [f"# Evidence bundle — order {r['order_id']} ({r['email']})", ""]
    if r.get("sender_unverified"):
        lines += ["> Note: the message had no sender address; check that this order's email is the person who wrote.", ""]
    if r.get("ignored_order"):
        lines += [f"> Note: {r['ignored_order']} was quoted in the message but belongs to another customer, so it was not read.", ""]
    lines += [f"**Finding:** {r['headline']}", "", f"**Root cause:** {r['explanation']}", "", "## Money chain"]
    for l in r["chain"]:
        lines.append(f"- [{l['state'].upper()}] {l['label']} — {l['note']}" + (f"  (refs: {', '.join(l['refs'])})" if l["refs"] else ""))
    jq = [q for q in r.get("queries", []) if q["tool"] == "order_journey"]
    if jq:
        lines += ["", f"## The query ({r.get('backend')})", "```sql", jq[-1]["sql"], "```"]
    lines += ["", "## Verified", *[f"- {v}" for v in r["verified"]], "", "## Not verified", *[f"- {u}" for u in r["unverified"]], "", "## Cited raw rows"]
    cited = {ref for l in r["chain"] for ref in l["refs"]}
    for table, rows in r["rows"].items():
        for row in rows:
            if row.get("ref") in cited:
                lines.append(f"- `{row['ref']}` " + json.dumps({k: v for k, v in row.items() if k != 'ref'}, default=str))
    lines += ["", f"_Generated by the verifier; SQL backend: {r['backend']}. All data in this demo is synthetic._"]
    return _out(PlainTextResponse("\n".join(lines), media_type="text/markdown"), sid, request)


@app.get("/api/health")
def health():
    from agent.sql_backend import get_backend
    db = SANDBOXES.shared() if PUBLIC else get_backend()
    return {"ok": True, "public": PUBLIC, "backend": db.name, "live_model": bool(os.getenv("NEBIUS_API_KEY"))}
