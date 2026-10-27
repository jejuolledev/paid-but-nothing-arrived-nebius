"""LLM_FAKE=1: a scripted stand-in with the OpenAI client's shape, for dry runs of the page, the recorder and the
tests without a key. It is not a model and every result made with it says "FAKE". Public mode refuses it."""
from __future__ import annotations
import json, re
from types import SimpleNamespace

MODEL = "FAKE-dry-run (not a model)"


def _resp(content: str, n_in: int):
    msg = SimpleNamespace(content=content, model_extra={})
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)], model=MODEL,
                           usage=SimpleNamespace(prompt_tokens=n_in // 4, completion_tokens=len(content) // 4), model_extra={})


class _Completions:
    def create(self, model=None, messages=None, **kw):
        system = messages[0]["content"]
        user = messages[-1]["content"]
        n_in = sum(len(m["content"]) for m in messages)
        if "You read one customer message" in system:
            return _resp(json.dumps(self._intake(user)), n_in)
        if "You investigate why a customer" in system:
            m = re.search(r"ord_\d{4}", user)
            return _resp(json.dumps({"thought": "fake", "done": True, "order_id": m.group(0) if m else ""}), n_in)
        payload = json.loads(user) if user.strip().startswith("{") else {}
        reds = [r for l in payload.get("chain", {}).get("links", []) if l.get("state") == "red" for r in l.get("refs", [])]
        ref = (reds or [r for l in payload.get("chain", {}).get("links", []) for r in l.get("refs", [])] or [""])[0]
        expl = f"FAKE dry-run text, not a model: the verifier marked this link [{ref}]." if ref else "FAKE dry-run text, not a model."
        return _resp(json.dumps({"explanation": expl, "customer_reply": "", "fix_action": ""}), n_in)

    @staticmethod
    def _intake(text: str) -> dict:
        phs = re.findall(r"EMAIL_\d+", text)
        m = re.search(r"(?:paid (?:[^.]{0,30} )?with|I am|I'm|this is|my email is|account is)\s+(EMAIL_\d+)", text, re.I)
        sender = m.group(1) if m else (phs[0] if phs else None)
        orders = re.findall(r"ord_\d{4}", text)
        plan = []
        if sender:
            plan += [{"tool": "find_orders", "args": {"email": sender}, "why": "orders under the sender's address"},
                     {"tool": "find_payments", "args": {"email": sender}, "why": "who paid at the payment provider"},
                     {"tool": "order_for_payment", "args": {"payment_id": "FROM_PAYMENTS"}, "why": "the order behind that payment"}]
        plan.append({"tool": "order_journey", "args": {"order_id": orders[0] if orders else "BEST_ORDER"}, "why": "full history"})
        return {"sender": sender, "other_people": [p for p in dict.fromkeys(phs) if p != sender], "order_ids": orders, "foreign_order_ids": [],
                "amount": ({"value": int(re.sub(r"[, ]", "", a.group(1))), "currency": "KRW"} if (a := re.search(r"(\d{1,3}(?:,\d{3})+) ?won", text)) else None), "paid_when": None, "pack": None, "complaint": "not_received", "wants": [],
                "language": "ko" if re.search(r"[가-힣]", text) else "en", "plan": plan}


class FakeOpenAI:
    def __init__(self):
        self.chat = SimpleNamespace(completions=_Completions())
