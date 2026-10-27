"""The money chain: five links, each verified against raw rows from a different source.

  card_authorized -> psp_paid -> order_created -> credit_granted -> mail_delivered

`verify()` is deterministic and citation-first: every link is green / red / grey and
carries the `ref`s of the rows that decided it. The language model explains and drafts;
it is not allowed to decide. That is what keeps the agent honest."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict

LINKS = ["card_authorized", "psp_paid", "order_created", "credit_granted", "mail_delivered"]
LABELS = {"card_authorized": "Card authorized", "psp_paid": "Payment provider: paid", "order_created": "Order confirmed",
          "credit_granted": "Credits granted", "mail_delivered": "Mail delivered"}


@dataclass
class Link:
    name: str
    state: str          # green | red | grey
    note: str
    refs: list[str] = field(default_factory=list)


@dataclass
class Verdict:
    order_id: str
    links: list[Link]
    broken: str | None
    headline: str
    verified: list[str]
    unverified: list[str]
    root_cause: str
    suggested_fix: str

    def to_dict(self):
        d = asdict(self); return d


def verify(journey: dict) -> Verdict:
    orders, pays, grants, logs, mails = (journey[k] for k in ("orders", "payments", "grants", "server_logs", "mail_events"))
    if not orders:
        return Verdict("", [Link(n, "grey", "no order found") for n in LINKS], None, "No order found for this customer.", [], ["order lookup"], "", "")
    o = orders[0]; oid = o["order_id"]
    verified, unverified, links = [], [], []
    paid = [p for p in pays if p["status"] == "PAID"]
    webhook_paid = [l for l in logs if l["route"].endswith("/webhook") and "PAID" in l["message"]]
    confirms = [l for l in logs if l["route"].endswith("/confirm")]
    grant_rows = [g for g in grants if g["status"] == "granted"]
    mail_sent = [m for m in mails if m["event"] in ("sent", "delivered")]
    mail_fail = [l for l in logs if l["route"].endswith("/mail/send") and l["http_status"] != "200"]

    # 1 card authorized / 2 PSP paid — one source: the PSP ledger
    if paid:
        links.append(Link("card_authorized", "green", f"Payment provider shows a PAID charge of {paid[-1]['amount']} {paid[-1]['currency']} (card •••• {paid[-1]['card_last4']})", [paid[-1]["ref"]]))
        links.append(Link("psp_paid", "green", "Payment provider status: PAID", [paid[-1]["ref"]]))
        verified.append(f"Charge exists at the payment provider ({paid[-1]['ref']})")
    else:
        only_start = all(l["route"].endswith("/checkout/start") for l in logs) if logs else True
        links.append(Link("card_authorized", "grey", "No charge at the payment provider for this order", []))
        links += [Link(n, "grey", "not reached", []) for n in LINKS[1:]]
        verified.append("No payment row at the payment provider for this order or email")
        unverified.append("Customer's card statement (not provided) — could confirm nothing was charged on their side")
        return Verdict(oid, links, None, "Nothing is broken. You were never charged.", verified, unverified,
                       "The checkout was started but never reached the card step" + (" (only /checkout/start in the logs)." if only_start else "."),
                       "No fix needed. Reply with reassurance and a fresh checkout link.")

    # 3 order confirmed — our DB + server log
    if o["status"] == "paid":
        links.append(Link("order_created", "green", "Order status paid in our database", [o["ref"]] + [c["ref"] for c in confirms[:1]]))
        verified.append(f"Order row is paid ({o['ref']})")
    else:
        refs = [o["ref"]] + [w["ref"] for w in webhook_paid[:1]] + [c["ref"] for c in confirms[:1]]
        if confirms and confirms[-1]["http_status"] == "409":
            note = f"Webhook PAID arrived, but /confirm returned 409 because the order row already said '{o['status']}' and the payment provider was not re-checked"
            cause = "A first attempt failed, the retry succeeded at the payment provider, and our confirm step trusted the stale 'failed' status instead of re-checking the payment provider. The reconcile job only scans pending orders, so nothing ever repaired it."
            fix = "Re-check the payment provider for this payment id and mark the order paid, then grant credits (requires approval). Code fix: confirm must re-query the payment provider when the local status is failed; reconcile must include failed orders with a PAID webhook."
        elif not confirms:
            note = f"Webhook PAID arrived, but no /confirm request was ever received; order stayed '{o['status']}'"
            cause = "The customer paid, the payment provider told us, but the client-side confirm call never happened — consistent with the confirm button being unreachable after payment."
            fix = "Confirm the order server-side from the PAID webhook and grant credits (requires approval). Code fix: never rely on a client click after a PAID webhook."
        else:
            note, cause, fix = f"Order status is '{o['status']}' despite a PAID charge", "Unknown — inspect the cited rows.", "Manual review."
        links.append(Link("order_created", "red", note, [r for r in refs if r]))
        links += [Link(n, "grey", "not reached", []) for n in LINKS[3:]]
        verified.append("Webhook PAID is in the server log" if webhook_paid else "No PAID webhook in the server log")
        unverified.append("Whether the customer saw an error screen (no client-side telemetry in these sources)")
        return Verdict(oid, links, "order_created", "Paid, but the order was never confirmed.", verified, unverified, cause, fix)

    # 4a credits went to the account that paid? (PSP payer vs order address)
    payer = (paid[-1].get("customer_email") or "").lower()
    if payer and payer != (o.get("email") or "").lower():
        bounced = [m for m in mails if m["event"] == "bounced"]
        refs = [paid[-1]["ref"], o["ref"]] + [g["ref"] for g in grant_rows[:1]] + [m["ref"] for m in bounced[:1]]
        links.append(Link("credit_granted", "red", f"Credits went to {o['email']}, but the card was paid by {paid[-1]['customer_email']}", refs))
        links.append(Link("mail_delivered", "red" if bounced else "grey", "Mail bounced at the order address" if bounced else "Mail went to the order address", [m["ref"] for m in bounced[:1]]))
        verified += [f"Payment provider payer is {paid[-1]['customer_email']} ({paid[-1]['ref']})", f"Order and grant use {o['email']} ({o['ref']})"]
        unverified.append("Whether the order address is a typo of the payer's address or a second account (ask the customer)")
        return Verdict(oid, links, "account_mismatch", "Paid, but the credits went to a different account.", verified, unverified,
                       "The order was placed under a different address than the one that paid (looks like a typo); credits and mail went to that address.",
                       "Move the credits to the payer's account after the customer confirms (requires approval). Code fix: prefill checkout with the signed-in address and warn on unknown domains.")

    # 4 credits granted — grants table
    if not grant_rows:
        links.append(Link("credit_granted", "red", "Order is paid but no grant row exists", [o["ref"]]))
        links.append(Link("mail_delivered", "grey", "not reached", []))
        return Verdict(oid, links, "credit_granted", "Paid and confirmed, but credits were never granted.", verified, unverified, "Grant step did not write a row.", "Grant credits (requires approval).")
    if len(grant_rows) > 1:
        refs = [g["ref"] for g in grant_rows] + [l["ref"] for l in logs if l["http_status"] == "504" or "retry" in l["route"]]
        links.append(Link("credit_granted", "red", f"{len(grant_rows)} grant rows for the same email and reward", refs))
        links.append(Link("mail_delivered", "green" if mail_sent else "grey", "Mail delivered" if mail_sent else "no mail event", [m["ref"] for m in mail_sent[-1:]]))
        verified.append(f"{len(grant_rows)} grants found ({', '.join(g['ref'] for g in grant_rows)})")
        return Verdict(oid, links, "credit_granted", "The customer received the credits twice.", verified, unverified,
                       "The first confirm timed out after the grant row was written; a manual retry granted again. There is no uniqueness constraint on (email, reward).",
                       "Revoke the duplicate grant (requires approval). Code fix: unique index on (email, reward_key, order_id); make the grant idempotent.")
    links.append(Link("credit_granted", "green", f"{grant_rows[0]['credits']} credits granted", [grant_rows[0]["ref"]]))
    verified.append(f"Grant row exists ({grant_rows[0]['ref']})")

    # 5 mail delivered — mail events + mail/send log
    if mail_sent:
        links.append(Link("mail_delivered", "green", f"Mail {mail_sent[-1]['event']}", [mail_sent[-1]["ref"]]))
        verified.append(f"Mail event {mail_sent[-1]['event']} ({mail_sent[-1]['ref']})")
        return Verdict(oid, links, None, "Everything went through. The credits are in the account.", verified,
                       ["Whether the mail landed in spam (provider reports delivered, not opened)"], "No broken link.", "Reply with where to find the credits.")
    refs = [l["ref"] for l in mail_fail] or [o["ref"]]
    links.append(Link("mail_delivered", "red", mail_fail[-1]["message"] if mail_fail else "No mail event for this order", refs))
    unverified.append("Customer's spam folder")
    return Verdict(oid, links, "mail_delivered", "Credits were granted, but the customer was never told.", verified, unverified,
                   "The mail send failed at the provider (" + (mail_fail[-1]["message"] if mail_fail else "no event") + "), so the customer has the credits but no notice.",
                   "Resend the credit mail (requires approval). Code fix: alert on mail/send errors and retry with backoff.")
