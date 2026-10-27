"""Synthetic data generator — four sources a small online seller would have to check by hand.

All data is synthetic. No real customer data. Emails use @example.com, card last4 are
Stripe public test numbers only. Deterministic seed so every run yields the same files.

Sources (mirroring the shapes of real systems, not their data):
  payments.csv     payment-service-provider ledger (Stripe-like)
  orders.csv       app database: orders
  grants.csv       app database: digital credit grants
  server_logs.csv  web server / webhook / cron log export
  mail_events.csv  transactional mail events (Resend-like; order_tag = order id)
Ground truth for the five seeded cases is written to cases.json.
"""
from __future__ import annotations
import csv, json, random
from datetime import datetime, timedelta
from pathlib import Path

OUT = Path(__file__).parent / "out"
SEED = 20261022
FIRST = ["mina","jun","sora","hana","yuna","dohyun","jiwoo","seojun","aria","noah","liam","emma","olivia","mason","ava","ethan","isla","leo","zoe","kai"]
LAST = ["park","kim","lee","choi","jung","cho","han","yoon","lim","song","smith","garcia","chen","patel","nguyen"]
TEST_LAST4 = ["4242","4444","0005","5556","1117","0004","8431","0341"]
REWARDS = [("lite10","Lite 10 credits",9900),("std30","Standard 30 credits",24900),("fam60","Family 60 credits",44900)]
T0 = datetime(2026,10,1,9,0,0)

def email(i: int, rnd: random.Random) -> str:
    return f"{rnd.choice(FIRST)}.{rnd.choice(LAST)}{i:03d}@example.com"

def ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

def main() -> None:
    rnd = random.Random(SEED)
    OUT.mkdir(parents=True, exist_ok=True)
    payments, orders, grants, logs, mails = [], [], [], [], []
    cases = []

    def normal_order(i: int, when: datetime, em: str, order_id: str, pay_id: str, reward):
        key, name, amount = reward
        payments.append(dict(payment_id=pay_id, amount=amount, currency="KRW", status="PAID",
                             card_last4=rnd.choice(TEST_LAST4), customer_email=em, created_at=ts(when)))
        orders.append(dict(order_id=order_id, payment_id=pay_id, email=em, reward_key=key, amount=amount,
                           status="paid", credited=1, created_at=ts(when), updated_at=ts(when+timedelta(seconds=9))))
        grants.append(dict(grant_id=f"g_{order_id}", email=em, reward_key=key, credits=int(key[-2:]), status="granted",
                           order_id=order_id, created_at=ts(when+timedelta(seconds=8))))
        logs.extend([dict(ts=ts(when+timedelta(seconds=2)), route="/api/payments/webhook", order_id=order_id, http_status=200, message="PSP webhook PAID"),
                 dict(ts=ts(when+timedelta(seconds=6)), route="/api/payments/confirm", order_id=order_id, http_status=200, message="confirmed; credits granted"),
                 dict(ts=ts(when+timedelta(seconds=9)), route="/api/mail/send", order_id=order_id, http_status=200, message="credit mail queued")])
        mid = f"m_{order_id}"
        mails.extend([dict(email_id=mid, to=em, event="sent", ts=ts(when+timedelta(seconds=10)), order_tag=order_id),
                  dict(email_id=mid, to=em, event="delivered", ts=ts(when+timedelta(seconds=25)), order_tag=order_id)])

    # 200 normal orders
    for i in range(1, 201):
        when = T0 + timedelta(minutes=rnd.randint(0, 20*24*60))
        normal_order(i, when, email(i, rnd), f"ord_{i:04d}", f"pay_{i:04d}", rnd.choice(REWARDS))

    # a few normal abandoned checkouts (never reached the card step)
    for i in range(201, 207):
        when = T0 + timedelta(minutes=rnd.randint(0, 20*24*60)); em = email(i, rnd); key, _, amount = rnd.choice(REWARDS)
        orders.append(dict(order_id=f"ord_{i:04d}", payment_id="", email=em, reward_key=key, amount=amount, status="pending", credited=0, created_at=ts(when), updated_at=ts(when)))
        logs.append(dict(ts=ts(when), route="/api/checkout/start", order_id=f"ord_{i:04d}", http_status=200, message="checkout started"))

    # ---- Case 1: paid but not credited (first attempt FAILED webhook, retry succeeded; confirm saw 'failed' and returned 409)
    when = T0 + timedelta(days=12, hours=3); em = "hana.lee901@example.com"; key, _, amount = REWARDS[1]
    payments.append(dict(payment_id="pay_0901", amount=amount, currency="KRW", status="PAID", card_last4="4242", customer_email=em, created_at=ts(when+timedelta(seconds=40))))
    orders.append(dict(order_id="ord_0901", payment_id="pay_0901", email=em, reward_key=key, amount=amount, status="failed", credited=0, created_at=ts(when), updated_at=ts(when+timedelta(seconds=5))))
    logs += [dict(ts=ts(when+timedelta(seconds=5)), route="/api/payments/webhook", order_id="ord_0901", http_status=200, message="PSP webhook FAILED (card declined, attempt 1)"),
             dict(ts=ts(when+timedelta(seconds=41)), route="/api/payments/webhook", order_id="ord_0901", http_status=200, message="PSP webhook PAID (attempt 2)"),
             dict(ts=ts(when+timedelta(seconds=44)), route="/api/payments/confirm", order_id="ord_0901", http_status=409, message="order status is failed; skipped PSP re-check"),
             dict(ts=ts(when+timedelta(days=1)), route="/api/cron/reconcile", order_id="", http_status=200, message="reconcile scanned status=pending only; 0 fixed")]
    cases.append(dict(case=1, title="Paid but not credited", email=em, order_id="ord_0901", broken_link="order_created",
                      expected="PSP ledger says PAID; our order row says failed; confirm returned 409 without re-checking the PSP; reconcile only scans pending. Credit was never granted."))

    # ---- Case 2: paid, confirm button blocked by the PSP overlay → no confirm request ever arrived
    when = T0 + timedelta(days=14, hours=11); em = "jun.park902@example.com"; key, _, amount = REWARDS[0]
    payments.append(dict(payment_id="pay_0902", amount=amount, currency="KRW", status="PAID", card_last4="4444", customer_email=em, created_at=ts(when+timedelta(seconds=30))))
    orders.append(dict(order_id="ord_0902", payment_id="pay_0902", email=em, reward_key=key, amount=amount, status="pending", credited=0, created_at=ts(when), updated_at=ts(when)))
    logs += [dict(ts=ts(when), route="/api/checkout/start", order_id="ord_0902", http_status=200, message="checkout started"),
             dict(ts=ts(when+timedelta(seconds=31)), route="/api/payments/webhook", order_id="ord_0902", http_status=200, message="PSP webhook PAID")]
    cases.append(dict(case=2, title="Paid, confirm never called", email=em, order_id="ord_0902", broken_link="order_created",
                      expected="PSP ledger says PAID and the webhook arrived, but there is no /api/payments/confirm request at all; order stayed pending, nothing granted."))

    # ---- Case 3: double grant (grant step timed out, admin retried, two grant rows)
    when = T0 + timedelta(days=15, hours=16); em = "sora.kim903@example.com"; key, _, amount = REWARDS[2]
    payments.append(dict(payment_id="pay_0903", amount=amount, currency="KRW", status="PAID", card_last4="0005", customer_email=em, created_at=ts(when)))
    orders.append(dict(order_id="ord_0903", payment_id="pay_0903", email=em, reward_key=key, amount=amount, status="paid", credited=1, created_at=ts(when), updated_at=ts(when+timedelta(minutes=3))))
    grants += [dict(grant_id="g_ord_0903", email=em, reward_key=key, credits=60, status="granted", order_id="ord_0903", created_at=ts(when+timedelta(seconds=70))),
               dict(grant_id="g_ord_0903_retry", email=em, reward_key=key, credits=60, status="granted", order_id="ord_0903", created_at=ts(when+timedelta(minutes=3)))]
    logs += [dict(ts=ts(when+timedelta(seconds=2)), route="/api/payments/webhook", order_id="ord_0903", http_status=200, message="PSP webhook PAID"),
             dict(ts=ts(when+timedelta(seconds=70)), route="/api/payments/confirm", order_id="ord_0903", http_status=504, message="grant batch timed out after 60s (row was written)"),
             dict(ts=ts(when+timedelta(minutes=3)), route="/api/admin/grants/retry", order_id="ord_0903", http_status=200, message="manual retry; granted again")]
    mid = "m_ord_0903"
    mails += [dict(email_id=mid, to=em, event="sent", ts=ts(when+timedelta(minutes=3, seconds=5)), order_tag="ord_0903"), dict(email_id=mid, to=em, event="delivered", ts=ts(when+timedelta(minutes=4)), order_tag="ord_0903")]
    cases.append(dict(case=3, title="Granted twice", email=em, order_id="ord_0903", broken_link="credit_granted",
                      expected="Two grant rows for the same email and reward; the first confirm timed out after writing, then a manual retry granted again."))

    # ---- Case 4: granted but the mail never went out (mail provider key missing)
    when = T0 + timedelta(days=17, hours=9); em = "noah.chen904@example.com"; key, _, amount = REWARDS[0]
    payments.append(dict(payment_id="pay_0904", amount=amount, currency="KRW", status="PAID", card_last4="1117", customer_email=em, created_at=ts(when)))
    orders.append(dict(order_id="ord_0904", payment_id="pay_0904", email=em, reward_key=key, amount=amount, status="paid", credited=1, created_at=ts(when), updated_at=ts(when+timedelta(seconds=9))))
    grants.append(dict(grant_id="g_ord_0904", email=em, reward_key=key, credits=10, status="granted", order_id="ord_0904", created_at=ts(when+timedelta(seconds=8))))
    logs += [dict(ts=ts(when+timedelta(seconds=2)), route="/api/payments/webhook", order_id="ord_0904", http_status=200, message="PSP webhook PAID"),
             dict(ts=ts(when+timedelta(seconds=6)), route="/api/payments/confirm", order_id="ord_0904", http_status=200, message="confirmed; credits granted"),
             dict(ts=ts(when+timedelta(seconds=9)), route="/api/mail/send", order_id="ord_0904", http_status=500, message="mail provider error: missing API key")]
    cases.append(dict(case=4, title="Granted, but no mail", email=em, order_id="ord_0904", broken_link="mail_delivered",
                      expected="Credits were granted, but /api/mail/send failed with a missing API key and there is no mail event for this order. The customer has the credits and does not know."))

    # ---- Case 5: never charged (abandoned before the card step) — nothing is broken
    when = T0 + timedelta(days=18, hours=20); em = "emma.song905@example.com"; key, _, amount = REWARDS[1]
    orders.append(dict(order_id="ord_0905", payment_id="", email=em, reward_key=key, amount=amount, status="pending", credited=0, created_at=ts(when), updated_at=ts(when)))
    logs.append(dict(ts=ts(when), route="/api/checkout/start", order_id="ord_0905", http_status=200, message="checkout started"))
    cases.append(dict(case=5, title="Never charged", email=em, order_id="ord_0905", broken_link=None,
                      expected="No PSP payment exists for this order; the customer left before the card step. Nothing is broken and nothing was charged."))

    # ---- Case 6: not in the verifier's playbook — paid with one email, ordered under a typo of it.
    # The customer writes from the right address; the orders table has nothing for it. Only the PSP
    # ledger knows the real address, and the grant went to the typo account. The agent has to find this.
    when = T0 + timedelta(days=19, hours=8); em = "liam.patel906@example.com"; typo = "liam.patel906@exmaple.com"; key, _, amount = REWARDS[1]
    payments.append(dict(payment_id="pay_0906", amount=amount, currency="KRW", status="PAID", card_last4="5556", customer_email=em, created_at=ts(when+timedelta(seconds=20))))
    orders.append(dict(order_id="ord_0906", payment_id="pay_0906", email=typo, reward_key=key, amount=amount, status="paid", credited=1, created_at=ts(when), updated_at=ts(when+timedelta(seconds=28))))
    grants.append(dict(grant_id="g_ord_0906", email=typo, reward_key=key, credits=30, status="granted", order_id="ord_0906", created_at=ts(when+timedelta(seconds=27))))
    logs += [dict(ts=ts(when+timedelta(seconds=21)), route="/api/payments/webhook", order_id="ord_0906", http_status=200, message="PSP webhook PAID"),
             dict(ts=ts(when+timedelta(seconds=26)), route="/api/payments/confirm", order_id="ord_0906", http_status=200, message="confirmed; credits granted"),
             dict(ts=ts(when+timedelta(seconds=29)), route="/api/mail/send", order_id="ord_0906", http_status=200, message="credit mail queued")]
    mails += [dict(email_id="m_ord_0906", to=typo, event="sent", ts=ts(when+timedelta(seconds=30)), order_tag="ord_0906"),
              dict(email_id="m_ord_0906", to=typo, event="bounced", ts=ts(when+timedelta(seconds=33)), order_tag="ord_0906")]
    cases.append(dict(case=6, title="Paid with one email, ordered under a typo", email=em, order_id="ord_0906", broken_link="account_mismatch",
                      expected="No order under the customer's address. The PSP ledger has pay_0906 PAID by liam.patel906@example.com; that payment belongs to ord_0906, placed under liam.patel906@exmaple.com (typo). Credits went to the typo account and the mail bounced. Nothing is lost: move the 30 credits to the right account."))

    def write(name, rows):
        with open(OUT / name, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    write("payments.csv", payments); write("orders.csv", orders); write("grants.csv", grants); write("server_logs.csv", logs); write("mail_events.csv", mails)
    (OUT / "cases.json").write_text(json.dumps(cases, indent=2))
    print(f"wrote {len(payments)} payments, {len(orders)} orders, {len(grants)} grants, {len(logs)} log lines, {len(mails)} mail events, {len(cases)} cases -> {OUT}")

if __name__ == "__main__":
    main()
