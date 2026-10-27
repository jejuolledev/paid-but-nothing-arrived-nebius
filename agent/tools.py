"""The read-only SQL tools the agent is allowed to call. Every row returned carries a
`ref` (source table + primary key) so any conclusion can cite the exact row."""
from __future__ import annotations
import re
from typing import Any

PK = {"payments": "payment_id", "orders": "order_id", "grants": "grant_id", "server_logs": "ts", "mail_events": "email_id"}
# columns of the order_journey semantic layer (zetaris/register.sql), used to un-join the one journey query
COLS = {
    "orders": ["order_id", "payment_id", "email", "reward_key", "amount", "status", "credited", "created_at", "updated_at"],
    "payments": ["payment_id", "amount", "currency", "status", "card_last4", "customer_email", "created_at"],
    "grants": ["grant_id", "email", "reward_key", "credits", "status", "order_id", "created_at"],
    "server_logs": ["ts", "route", "order_id", "http_status", "message"],
    "mail_events": ["email_id", "to_address", "event", "ts", "order_tag"],
}
_ALIAS = {"o": "orders", "p": "payments", "g": "grants", "l": "server_logs", "m": "mail_events"}
SORT = {"payments": "created_at", "grants": "created_at", "server_logs": "ts", "mail_events": "ts"}


def _tag(table: str, rows: list[dict]) -> list[dict]:
    for r in rows:
        key = PK[table]
        if table == "server_logs":
            r["ref"] = f"server_logs:{r.get('ts')}@{r.get('route')}"
        elif table == "mail_events":  # one mail id has several events (sent, bounced): the event makes the row unique
            r["ref"] = f"mail_events:{r.get(key)}@{r.get('event')}"
        else:
            r["ref"] = f"{table}:{r.get(key)}"
    return rows


_SAFE = {
    "order_id": re.compile(r"ord_\d{4}"),
    "email": re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+"),
    "payment_id": re.compile(r"pay_[\w-]{1,40}"),
    "reward_key": re.compile(r"[\w-]{1,40}"),
}


def lit(kind: str, value: str) -> str:
    """Only well-formed ids reach SQL; anything else is refused, never escaped-and-hoped."""
    if not _SAFE[kind].fullmatch(str(value or "")):
        raise ValueError(f"rejected {kind}")
    return "'" + str(value) + "'"


class Tools:
    def __init__(self, backend):
        self.db = backend
        self.sql_log: list[dict[str, Any]] = []  # every statement sent through the SQL door, in order

    def _q(self, tool: str, sql: str) -> list[dict[str, Any]]:
        rows = self.db.query(sql)
        self.sql_log.append({"tool": tool, "sql": sql, "rows": len(rows), "backend": getattr(self.db, "name", "")})
        return rows

    def find_orders(self, email: str = "", order_id: str = "") -> list[dict[str, Any]]:
        """Orders for a customer email or an order id (most recent first)."""
        where = f"order_id = {lit('order_id', order_id)}" if order_id else f"lower(email) = lower({lit('email', email)})"
        return _tag("orders", self._q("find_orders", f"SELECT * FROM orders WHERE {where} ORDER BY created_at DESC LIMIT 10"))

    def order_journey(self, order_id: str) -> dict[str, list[dict[str, Any]]]:
        """Every row from every source that mentions this order — fetched with ONE query that joins the
        five tables of the semantic layer (orders ⟕ payments ⟕ grants ⟕ server_logs ⟕ mail_events),
        then split back into per-source rows so each one can still be cited as `table:key`."""
        oid = lit("order_id", order_id)
        cols = ", ".join(f"{a}.{c} AS {a}__{c}" for a, t in _ALIAS.items() for c in COLS[t])
        sql = (f"SELECT {cols} FROM orders o "
               "LEFT JOIN payments p ON p.payment_id = o.payment_id "
               "LEFT JOIN grants g ON g.order_id = o.order_id "
               "LEFT JOIN server_logs l ON l.order_id = o.order_id "
               "LEFT JOIN mail_events m ON m.order_tag = o.order_id "
               f"WHERE o.order_id = {oid}")
        flat = self._q("order_journey", sql)
        out: dict[str, list[dict[str, Any]]] = {t: [] for t in _ALIAS.values()}
        seen: set[str] = set()
        for r in flat:
            for a, t in _ALIAS.items():
                row = {c: r.get(f"{a}__{c}") for c in COLS[t]}
                if row[PK[t]] is None:
                    continue  # no row in this source for this order (LEFT JOIN miss)
                ref = _tag(t, [row])[0]["ref"]
                if ref not in seen:
                    seen.add(ref); out[t].append(row)
        for t, key in SORT.items():
            out[t].sort(key=lambda x: str(x.get(key) or ""))
        return out

    def find_payments(self, email: str) -> list[dict[str, Any]]:
        """PSP ledger rows paid by this email — the PSP knows the payer even when our order row has a different address."""
        return _tag("payments", self._q("find_payments", f"SELECT * FROM payments WHERE lower(customer_email) = lower({lit('email', email)}) ORDER BY created_at DESC LIMIT 10"))

    def order_for_payment(self, payment_id: str) -> list[dict[str, Any]]:
        """The order row that a PSP payment belongs to."""
        return _tag("orders", self._q("order_for_payment", f"SELECT * FROM orders WHERE payment_id = {lit('payment_id', payment_id)}"))

    def related_orders(self, email: str) -> list[dict[str, Any]]:
        """Other orders by the same email — catches duplicates and account-mismatch cases."""
        return _tag("orders", self._q("related_orders", f"SELECT * FROM orders WHERE lower(email) = lower({lit('email', email)}) ORDER BY created_at DESC LIMIT 20"))


OPENAI_TOOLS = [
    {"type": "function", "function": {"name": "find_orders", "description": "Find orders by customer email or order id.",
        "parameters": {"type": "object", "properties": {"email": {"type": "string"}, "order_id": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "order_journey", "description": "Fetch every row from the payment ledger, orders, grants, server logs and mail events for one order.",
        "parameters": {"type": "object", "properties": {"order_id": {"type": "string"}}, "required": ["order_id"]}}},
    {"type": "function", "function": {"name": "related_orders", "description": "List other orders by the same email.",
        "parameters": {"type": "object", "properties": {"email": {"type": "string"}}, "required": ["email"]}}},
]
