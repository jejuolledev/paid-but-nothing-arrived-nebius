"""The investigation loop: the model decides which records to pull next.

Nemotron (called through Meterless Nightshift on the seller's Mac) gets the customer's message and a small set of
read-only tools over the Zetaris layer. Each turn it answers with one JSON action — call a tool, or
stop and name the order it believes the complaint is about. It never writes anything and never
decides the verdict: once it names an order, the deterministic verifier walks the money chain and
the result is checked against the rows the model actually saw.

Customer identity is aliased before anything reaches the model: the address the customer wrote from
becomes `CUSTOMER`, any other address keeps only its first letter and its domain (so a typo such as
`exmaple.com` stays visible), and card digits are dropped.
"""
from __future__ import annotations
import json, os, re, time

MAX_STEPS = 6
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")

TOOLS_DOC = """Tools (all read-only, all go through one SQL layer):
- find_orders {"email": "CUSTOMER"} or {"order_id": "ord_0000"}: our order rows
- find_payments {"email": "CUSTOMER"}: the payment provider's ledger rows paid by that address
- order_for_payment {"payment_id": "pay_0000"}: the order a payment belongs to
- order_journey {"order_id": "ord_0000"}: every payment, grant, server-log and mail row for one order
- related_orders {"email": "CUSTOMER"}: other orders by the same address"""

SYSTEM = (
    "You investigate why a customer of a small online shop says they paid but nothing arrived. "
    "Use the tools to find which order the complaint is about and what happened to it. Think in short steps. "
    "Reply with ONE JSON object per turn and nothing else:\n"
    '{"thought": "<one sentence>", "tool": "<name>", "args": {...}}  to look something up, or\n'
    '{"thought": "<one sentence>", "done": true, "order_id": "ord_0000", "finding": "<what happened, citing refs like [payments:pay_0000]>"}\n'
    "Rules: use only refs that appeared in tool results; if the customer has no order under their address, "
    "remember the payment provider knows who paid; never guess an order id you have not seen.\n" + TOOLS_DOC
)


class Aliaser:
    def __init__(self, customer_email: str):
        self.customer = (customer_email or "").lower()

    def email(self, e: str) -> str:
        e = (e or "").lower()
        if not e:
            return e
        if self.customer and e == self.customer:
            return "CUSTOMER"
        local, _, domain = e.partition("@")
        return f"{local[:1]}***@{domain}"

    def rows(self, rows: list[dict]) -> list[dict]:
        out = []
        for r in rows:
            r2 = {}
            for k, v in r.items():
                if k == "card_last4":
                    continue
                if isinstance(v, str) and EMAIL_RE.fullmatch(v):
                    v = self.email(v)
                r2[k] = v
            out.append(r2)
        return out

    def arg(self, v: str) -> str:
        return self.customer if v == "CUSTOMER" else v



class Scope:
    """The sender's own trail: their address, payments made by it, and orders that belong to it (by order address
    or by payer). Lookups outside it are refused, so a crafted message cannot steer a model (loop or plan) into
    another customer's records. Tool args use "CUSTOMER" for the sender's address."""
    TOOLS = ("find_orders", "find_payments", "order_for_payment", "order_journey", "related_orders")

    def __init__(self, customer_email: str, tools, seed_order: str = ""):
        self.cust = (customer_email or "").lower()
        self.tools = tools
        self.mine_pay: set[str] = set()
        self.mine_ord: set[str] = {seed_order} if seed_order else set()  # the seller pasted this order id

    def _addr(self, a):
        if a.get("email", "CUSTOMER") != "CUSTOMER":
            raise PermissionError("only CUSTOMER may be looked up")
        return self.cust

    def _owned_order(self, oid):
        if oid not in self.mine_ord:
            raise PermissionError("that order is not on this customer's trail")
        return oid

    def _pay(self, a):
        pid = a.get("payment_id", "")
        if pid not in self.mine_pay:
            raise PermissionError("that payment was not made by this customer")
        return pid

    def _note(self, rows):
        for r in rows:
            if r.get("ref", "").startswith("payments:") and (r.get("customer_email") or "").lower() == self.cust:
                self.mine_pay.add(r["payment_id"])
            if r.get("ref", "").startswith("orders:") and ((r.get("email") or "").lower() == self.cust or r.get("payment_id") in self.mine_pay):
                self.mine_ord.add(r["order_id"])
        return rows

    def call(self, name: str, a: dict):
        t = self.tools
        if name == "find_orders":
            if a.get("order_id") and "email" not in a:
                rows = t.find_orders(order_id=a["order_id"])
                # an order number only joins the trail if it belongs to the sender (order address or payer)
                return self._note([r for r in rows if (r.get("email") or "").lower() == self.cust or r.get("payment_id") in self.mine_pay or r["order_id"] in self.mine_ord])
            return self._note(t.find_orders(email=self._addr(a)))
        if name == "find_payments":
            return self._note(t.find_payments(self._addr(a)))
        if name == "order_for_payment":
            return self._note(t.order_for_payment(self._pay(a)))
        if name == "order_journey":
            return t.order_journey(self._owned_order(a.get("order_id", "")))
        if name == "related_orders":
            return self._note(t.related_orders(self._addr(a)))
        raise KeyError(name)

def meterless_receipt(resp) -> dict | None:
    """Meterless Nightshift attaches a compute receipt to every answer (which model actually ran,
    under which mode). Keep it so the screen can show what ran — None when not routed through Nightshift."""
    extra = getattr(resp, "model_extra", None) or {}
    m = extra.get("meterless")
    if not m:
        return None
    return {k: m.get(k) for k in ("receipt_id", "decision_id", "requested_model", "provider_model", "mode") if m.get(k)} | {"model": getattr(resp, "model", None)}


def _parse(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def investigate_loop(client, model: str, message: str, customer_email: str, tools, seed_order: str = "") -> dict:
    """Returns {order_id, finding, steps, seen_refs, ok}. `steps` is what the screen and the video show."""
    al = Aliaser(customer_email)
    scope = Scope(customer_email, tools, seed_order)
    calls = {name: (lambda a, n=name: scope.call(n, a)) for name in Scope.TOOLS}
    from .investigator import mask_card_digits
    safe_msg = mask_card_digits(EMAIL_RE.sub(lambda m: al.email(m.group(0)), message[:2000]))
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Customer message: {safe_msg}\nThe customer wrote from: CUSTOMER" + (f"\nThe seller says the order is {seed_order}." if seed_order else "")}]
    steps, seen, seen_orders = [], set(), set()
    for _ in range(MAX_STEPS):
        t0 = time.time()
        resp = client.chat.completions.create(**({"_role": "loop"} if hasattr(client, "log") else {}), model=model, temperature=0.1, messages=msgs, max_tokens=3000, reasoning_effort=os.getenv("LLM_REASONING", "none"))
        text = resp.choices[0].message.content or ""
        receipt = meterless_receipt(resp)
        act = _parse(text)
        if not act:
            steps.append({"thought": "(unreadable reply)", "ms": int((time.time() - t0) * 1000)})
            msgs += [{"role": "assistant", "content": text}, {"role": "user", "content": "Reply with one JSON object only."}]
            continue
        if act.get("done"):
            oid = act.get("order_id", "")
            ok = oid in scope.mine_ord
            steps.append({"thought": act.get("thought", ""), "done": True, "order_id": oid, "ms": int((time.time() - t0) * 1000), "receipt": receipt})
            return {"ok": ok, "order_id": oid if ok else "", "finding": act.get("finding", ""), "steps": steps, "seen_refs": sorted(seen)}
        name, args = act.get("tool", ""), act.get("args", {}) or {}
        n0 = len(tools.sql_log)
        try:
            result = calls[name](args)
            rows = [r for v in result.values() for r in v] if isinstance(result, dict) else result
            seen.update(r["ref"] for r in rows)
            seen_orders.update(r["order_id"] for r in rows if r.get("order_id"))
            shown = {k: al.rows(v) for k, v in result.items()} if isinstance(result, dict) else al.rows(result)
            obs = json.dumps(shown, default=str)[:6000]
            obs = EMAIL_RE.sub(lambda m: al.email(m.group(0)), obs)  # also addresses inside free text (e.g. a log message)
            steps.append({"thought": act.get("thought", ""), "tool": name, "args": args, "rows": len(rows), "ms": int((time.time() - t0) * 1000), "receipt": receipt,
                          "sql": [q["sql"] for q in tools.sql_log[n0:]]})
        except (KeyError, ValueError, PermissionError) as e:
            obs = f"refused: {e}" if isinstance(e, PermissionError) else f"error: {type(e).__name__} — check the tool name and arguments"
            steps.append({"thought": act.get("thought", ""), "tool": name, "args": args, "error": True,
                          "refused": isinstance(e, PermissionError), "ms": int((time.time() - t0) * 1000)})
        msgs += [{"role": "assistant", "content": json.dumps(act)}, {"role": "user", "content": f"Result of {name}: {obs}"}]
    return {"ok": False, "order_id": "", "finding": "", "steps": steps, "seen_refs": sorted(seen)}
