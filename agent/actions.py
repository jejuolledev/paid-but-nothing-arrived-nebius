"""Human-approved fix actions. The agent only suggests; a person must approve before anything is written."""
from __future__ import annotations
import re
from datetime import datetime, timezone

from .chain import verify
from .investigator import investigate
from .tools import Tools, lit

READONLY_MSG = (
    "This backend is read-only (Zetaris federates sources; fixes go to the seller's own systems). "
    "Run the offline demo to see approval end to end."
)


class ReadOnlyBackend(Exception):
    """Zetaris (and any backend without execute) cannot apply local writes."""


class NothingToFix(Exception):
    """Chain is already healthy — nothing for approval to do."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _credits(reward_key: str) -> str:
    m = re.search(r"(\d+)$", reward_key or "")
    return m.group(1) if m else "0"


class NeedsCustomerConfirmation(Exception):
    """Moving credits to another address needs the customer's yes first."""


def approve(order_id: str, approved_by: str = "seller", backend=None, customer_confirmed: bool = False) -> dict:
    """Apply the verifier's suggested fix for one order, audit it, then re-investigate.
    The whole check-then-write runs under the backend lock, so two clicks cannot both apply."""
    from .sql_backend import get_backend
    db = backend or get_backend()
    lock = getattr(db, "lock", None)
    if lock is None or not hasattr(db, "execute"):
        raise ReadOnlyBackend(READONLY_MSG)
    with lock:
        return _approve(order_id, approved_by, db, customer_confirmed)


def _approve(order_id: str, approved_by: str, backend, customer_confirmed: bool) -> dict:
    from .sql_backend import get_backend
    db = backend or get_backend()
    if not hasattr(db, "execute"):
        raise ReadOnlyBackend(READONLY_MSG)
    oid_lit = lit("order_id", order_id)  # validates ord_\d{4}
    approved_by = (approved_by or "seller").strip() or "seller"
    tools = Tools(db)
    journey = tools.order_journey(order_id)
    verdict = verify(journey)
    if not journey["orders"] or verdict.broken is None:
        raise NothingToFix("Nothing to fix")

    kind = verdict.broken
    if kind == "account_mismatch" and not customer_confirmed:
        raise NeedsCustomerConfirmation("Ask the customer to confirm the address they paid with, then approve again.")
    o = journey["orders"][0]
    ts = _now()
    lock = getattr(db, "lock", None)
    if lock is None:
        raise ReadOnlyBackend(READONLY_MSG)
    with lock:  # one fix at a time, all-or-nothing
        db.execute("BEGIN TRANSACTION")
        try:
            applied = _apply(db, kind, order_id, oid_lit, o, journey, ts)
            db.execute("COMMIT")
        except Exception:
            db.execute("ROLLBACK")
            raise
    action_id = f"a_{order_id}_{ts.replace(':', '').replace('-', '')}"
    detail = applied["detail"]
    # approved_by is a short free-text label from the seller UI; keep it SQL-safe.
    by = re.sub(r"[^A-Za-z0-9_@.+-]", "", approved_by)[:40] or "seller"
    db.execute(
        f"INSERT INTO actions VALUES ('{action_id}', {oid_lit}, '{kind}', "
        f"'{detail.replace(chr(39), '')}', '{by}', '{ts}')"
    )
    audit = db.query(f"SELECT * FROM actions WHERE action_id = '{action_id}'")[0]
    # re-check with the verifier only: the chain is deterministic, and the seller should not wait on a model
    after = investigate(f"order {order_id}", order_id=order_id, backend=db, use_model=False)
    after["sender_unverified"] = False  # the seller is re-checking an order already tied to its sender
    return {"applied": applied, "audit": audit, "after": after}


def _apply(db, kind: str, order_id: str, oid_lit: str, o: dict, journey: dict, ts: str) -> dict:
    if kind == "order_created":
        email, rk = o["email"], o["reward_key"]
        credits = _credits(rk)
        em, rk_lit = lit("email", email), lit("reward_key", rk)
        grant_id = f"g_{order_id}_fix"
        mail_id = f"m_{order_id}_fix"
        db.execute(
            f"UPDATE orders SET status = 'paid', credited = '1', updated_at = '{ts}' "
            f"WHERE order_id = {oid_lit}"
        )
        db.execute(
            f"INSERT INTO grants VALUES ('{grant_id}', {em}, {rk_lit}, '{credits}', "
            f"'granted', {oid_lit}, '{ts}')"
        )
        db.execute(
            f"INSERT INTO mail_events VALUES ('{mail_id}', {em}, 'sent', '{ts}', {oid_lit})"
        )
        return {"kind": kind, "detail": f"marked {order_id} paid, granted {credits}, mailed notice"}

    if kind == "credit_granted":
        granted = [g for g in journey["grants"] if g.get("status") == "granted"]
        if len(granted) < 2:
            raise NothingToFix("Nothing to fix")
        newest = sorted(granted, key=lambda g: g.get("created_at") or "")[-1]
        gid = newest["grant_id"]
        if not re.fullmatch(r"g_[\w-]+", gid):
            raise ValueError("rejected grant_id")
        db.execute(f"UPDATE grants SET status = 'revoked' WHERE grant_id = '{gid}'")
        return {"kind": kind, "detail": f"revoked duplicate grant {gid}"}

    if kind == "mail_delivered":
        email = o["email"]
        em = lit("email", email)
        mail_id = f"m_{order_id}_fix"
        db.execute(
            f"INSERT INTO mail_events VALUES ('{mail_id}', {em}, 'sent', '{ts}', {oid_lit})"
        )
        return {"kind": kind, "detail": f"queued the credit mail again for {order_id} (offline demo: no real mail leaves this machine)"}

    if kind == "account_mismatch":
        pays = [p for p in journey["payments"] if p.get("status") == "PAID"]
        if not pays:
            raise NothingToFix("Nothing to fix")
        payer = pays[-1]["customer_email"]
        em = lit("email", payer)
        db.execute(f"UPDATE orders SET email = {em}, updated_at = '{ts}' WHERE order_id = {oid_lit}")
        db.execute(f"UPDATE grants SET email = {em} WHERE order_id = {oid_lit}")
        mail_id = f"m_{order_id}_fix"
        db.execute(
            f"INSERT INTO mail_events VALUES ('{mail_id}', {em}, 'sent', '{ts}', {oid_lit})"
        )
        return {"kind": kind, "detail": f"moved credits and mail to {payer}"}

    raise NothingToFix("Nothing to fix")
