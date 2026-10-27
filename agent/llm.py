"""Model access: NVIDIA Nemotron on Nebius Token Factory (OpenAI-compatible), with a record of every call.

Configuration (all from the environment, normally `.env.local`, never committed):
  NEBIUS_API_KEY        Token Factory API key. Setting it is the operator's opt-in to send masked rows to Token Factory.
  LLM_BASE_URL          default https://api.tokenfactory.nebius.com/v1/
  LLM_MODEL             default model for every role (default nvidia/nemotron-3-super-120b-a12b)
  LLM_MODEL_INTAKE      model that reads the customer's message and plans the lookups (falls back to LLM_MODEL)
  LLM_MODEL_EXPLAIN     model that writes the cited explanation and the reply draft (falls back to LLM_MODEL)
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
    return os.getenv(f"LLM_MODEL_{role.upper()}") or os.getenv("LLM_MODEL") or DEFAULT_MODEL


def strip_thinking(text: str) -> str:
    """Reasoning models may prepend <think>…</think>; only the answer after it is used."""
    text = THINK_RE.sub("", text or "")
    if "</think>" in text:  # an unterminated opening tag was cut off by the endpoint
        text = text.split("</think>", 1)[1]
    return text.strip()


class CallLog(list):
    """Every model call of one investigation: role, model, provider, latency, tokens, outcome."""

    def add(self, **kw):
        self.append(kw)

    def summary(self) -> dict:
        ok = [c for c in self if c.get("ok")]
        return {"calls": len(self), "ok": len(ok),
                "prompt_tokens": sum(c.get("prompt_tokens") or 0 for c in self),
                "completion_tokens": sum(c.get("completion_tokens") or 0 for c in self),
                "ms": sum(c.get("ms") or 0 for c in self)}


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
        self.log.add(role=_role, model=getattr(resp, "model", None) or kw.get("model"), requested_model=kw.get("model"),
                     provider=self.provider, ok=True, ms=int((time.time() - t0) * 1000),
                     prompt_tokens=getattr(u, "prompt_tokens", None), completion_tokens=getattr(u, "completion_tokens", None))
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
