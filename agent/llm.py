"""Model access: NVIDIA Nemotron on Nebius Token Factory (OpenAI-compatible), with a record of every call.

Configuration (all from the environment, normally `.env.local`, never committed):
  NEBIUS_API_KEY        Token Factory API key. Setting it is the operator's opt-in to send masked rows to Token Factory.
  LLM_BASE_URL          default https://api.tokenfactory.nebius.com/v1/
  Different models per job (the routing table, ROUTES below). Per role: LLM_MODEL_<ROLE>, else LLM_MODEL (one text
  model for every text role), else the role's default:
    vision    LLM_VISION_MODEL / LLM_MODEL_VISION  reads the customer's payment screenshot  (Nemotron 3.5 Super VL)
    intake    LLM_MODEL_INTAKE    reads the message and plans the read-only lookups    (Nemotron 3.5 Lightning)
    escalate  LLM_MODEL_ESCALATE  re-reads the message only when the first reader is unsure (Nemotron 3 Ultra)
    explain   LLM_MODEL_EXPLAIN   writes the cited explanation and the reply draft     (Nemotron 3 Super)
  The vision role never falls back to LLM_MODEL (a text model cannot read a photo).
  LLM_TIMEOUT           seconds per call (default 60)
  LLM_EXTRA_BODY        optional JSON merged into each request, e.g. {"chat_template_kwargs": {"enable_thinking": false}}
  LLM_REASONING         optional reasoning_effort value; sent only when set
  LLM_FAKE=1            dry run with a scripted stand-in (no network, labelled "FAKE" everywhere; refused in public mode)

The older local path (Meterless Nightshift on the seller's Mac) still works through NIGHTSHIFT_BASE_URL; see
docs/open-agent-2026-10-25/. Nothing in this module decides a verdict: models read, plan and write; code decides.
"""
from __future__ import annotations
import json, os, re, time

TOKEN_FACTORY_URL = "https://api.tokenfactory.nebius.com/v1/"
DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b"   # listed on nebius.com/services/token-factory/nemotron
# Defaults per job. Ids from the public Token Factory catalog (tokenfactory.nebius.com/api/public/models_info, 2026-10-27);
# confirm with scripts/tf_models.py once a key exists. Fast cheap reader first, Ultra only when the reader is unsure.
ROUTES = {
    "vision": "nvidia/Nemotron-3.5-Super-VL",
    "intake": "nvidia/Nemotron-3_5-Lightning",
    "escalate": "nvidia/Nemotron-3-Ultra-550b-a55b",
    "explain": DEFAULT_MODEL,
    "reply": DEFAULT_MODEL,
}
# USD per 1M tokens (input, output), same catalog. Used only to show cost per case; the bill is Token Factory's.
PRICES = {
    "nvidia/nvidia-nemotron-3-nano-30b-a3b": (0.06, 0.24),
    "nvidia/nemotron-3_5-lightning": (0.06, 0.24),
    "nvidia/nemotron-3-super-120b-a12b": (0.30, 0.90),
    "nvidia/nemotron-3-ultra-550b-a55b": (1.00, 3.00),
    "nvidia/nemotron-3.5-super-vl": (0.30, 0.90),
}


def cost_usd(model: str | None, prompt_tokens, completion_tokens) -> float | None:
    p = PRICES.get(str(model or "").lower())
    if not p or prompt_tokens is None:
        return None
    return round(((prompt_tokens or 0) * p[0] + (completion_tokens or 0) * p[1]) / 1e6, 6)
THINK_RE = re.compile(r"<think>.*?</think>", re.S)


def provider_name(base: str | None) -> str:
    if os.getenv("LLM_FAKE") == "1":
        return "FAKE (dry run, no model)"
    if base and "nebius.com" in base:
        return "Nebius Token Factory"
    if os.getenv("NIGHTSHIFT_BASE_URL"):
        return "Meterless Nightshift (local)"
    return "OpenAI-compatible endpoint"


def model_for(role: str) -> str:
    if role == "vision":
        return os.getenv("LLM_VISION_MODEL") or os.getenv("LLM_MODEL_VISION") or ROUTES["vision"]
    return os.getenv(f"LLM_MODEL_{role.upper()}") or os.getenv("LLM_MODEL") or ROUTES.get(role, DEFAULT_MODEL)


def strip_thinking(text: str) -> str:
    """Reasoning models may prepend <think>…</think>; only the answer after it is used."""
    text = THINK_RE.sub("", text or "")
    if "</think>" in text:  # an unterminated opening tag was cut off by the endpoint
        text = text.split("</think>", 1)[1]
    return text.strip()


SPEND_LEDGER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "build", "spend_ledger.jsonl")


class BudgetExceeded(RuntimeError):
    pass


def spent_usd() -> float:
    """Total estimated spend of every real Token Factory call made from this checkout (build/spend_ledger.jsonl)."""
    try:
        with open(SPEND_LEDGER) as f:
            return round(sum(json.loads(l).get("usd") or 0 for l in f if l.strip()), 6)
    except FileNotFoundError:
        return 0.0


def _record_spend(entry: dict):
    os.makedirs(os.path.dirname(SPEND_LEDGER), exist_ok=True)
    with open(SPEND_LEDGER, "a") as f:
        f.write(json.dumps(entry) + "\n")


class CallLog(list):
    """Every model call of one investigation: role, model, provider, latency, tokens, outcome."""

    def add(self, **kw):
        self.append(kw)

    def summary(self) -> dict:
        ok = [c for c in self if c.get("ok")]
        return {"calls": len(self), "ok": len(ok),
                "prompt_tokens": sum(c.get("prompt_tokens") or 0 for c in self),
                "completion_tokens": sum(c.get("completion_tokens") or 0 for c in self),
                "ms": sum(c.get("ms") or 0 for c in self),
                "usd": round(sum(c.get("usd") or 0 for c in self), 6)}


class TracedClient:
    """Wraps an OpenAI client: `create(..., _role="intake")` records the call in `log` and strips <think> blocks.
    Exposes .chat.completions.create like the real client so existing code keeps working."""

    def __init__(self, client, log: CallLog, provider: str):
        self._client, self.log, self.provider = client, log, provider
        self.chat = self
        self.completions = self

    def create(self, _role: str = "call", **kw):
        extra = os.getenv("LLM_EXTRA_BODY")
        if extra:
            kw["extra_body"] = {**json.loads(extra), **kw.get("extra_body", {})}
        if "reasoning_effort" in kw and not os.getenv("LLM_REASONING"):
            kw.pop("reasoning_effort")
        real = type(self._client).__module__.startswith("openai")  # a real HTTP client, not a test stand-in or the fake
        budget = os.getenv("LLM_BUDGET_USD")
        if real and budget and spent_usd() >= float(budget):
            raise BudgetExceeded(f"spend ledger at ${spent_usd():.4f} >= budget ${float(budget):.2f}; stopping before the call")
        t0 = time.time()
        try:
            resp = self._client.chat.completions.create(**kw)
        except Exception as e:
            self.log.add(role=_role, model=kw.get("model"), provider=self.provider, ok=False,
                         ms=int((time.time() - t0) * 1000), error=f"{type(e).__name__}"[:80])
            raise
        u = getattr(resp, "usage", None)
        msg = resp.choices[0].message
        raw = msg.content or ""
        if not raw.strip():  # some reasoning endpoints put the whole answer in reasoning_content
            raw = getattr(msg, "reasoning_content", None) or (getattr(msg, "model_extra", None) or {}).get("reasoning_content") or ""
        msg.content = strip_thinking(raw)
        pt, ct = getattr(u, "prompt_tokens", None), getattr(u, "completion_tokens", None)
        self.log.add(role=_role, model=getattr(resp, "model", None) or kw.get("model"), requested_model=kw.get("model"),
                     provider=self.provider, ok=True, ms=int((time.time() - t0) * 1000),
                     prompt_tokens=pt, completion_tokens=ct, usd=cost_usd(kw.get("model"), pt, ct))
        if real:
            _record_spend({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "role": _role, "model": kw.get("model"), "prompt_tokens": pt,
                           "completion_tokens": ct, "usd": cost_usd(kw.get("model"), pt, ct), "ms": self.log[-1]["ms"]})
        return resp


def token_factory_client(log: CallLog | None = None, timeout: float | None = None):
    """(TracedClient, provider) for Token Factory, the fake stand-in, or (None, reason)."""
    log = log if log is not None else CallLog()
    if os.getenv("LLM_FAKE") == "1":
        from .fake_llm import FakeOpenAI
        return TracedClient(FakeOpenAI(), log, provider_name(None)), provider_name(None)
    key = os.getenv("NEBIUS_API_KEY")
    if not key:
        return None, "no NEBIUS_API_KEY"
    from openai import OpenAI
    base = os.getenv("LLM_BASE_URL") or TOKEN_FACTORY_URL
    t = timeout or float(os.getenv("LLM_TIMEOUT", "60"))
    return TracedClient(OpenAI(base_url=base, api_key=key, timeout=t, max_retries=0), log, provider_name(base)), provider_name(base)
