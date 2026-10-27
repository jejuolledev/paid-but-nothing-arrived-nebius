"""How well does the per-sentence claim check separate true explanations from wrong ones?

Runs `_claims_ok` on hand-written sentences about the six seeded cases: TRUE ones (what a correct explanation
says, including sentences the model actually wrote in measured runs) and FALSE ones (a real citation, but a wrong
amount, id, credit count, payment / credit / mail state, or language). Prints caught / wrongly-rejected counts and
appends a line to docs/measurements.md.

Run: .venv/bin/python scripts/claim_eval.py
"""
from __future__ import annotations
import sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agent.sql_backend import DuckDBBackend  # noqa: E402
from agent.tools import Tools  # noqa: E402
from agent.investigator import _claims_ok  # noqa: E402

t = Tools(DuckDBBackend())
ROWS = {r["ref"]: r for o in ["ord_0901", "ord_0902", "ord_0903", "ord_0904", "ord_0905", "ord_0906"]
        for rows in t.order_journey(o).values() for r in rows}

P1, O1 = "[payments:pay_0901]", "[orders:ord_0901]"
L1a, L1c = "[server_logs:2026-10-13T12:00:05Z@/api/payments/webhook]", "[server_logs:2026-10-13T12:00:44Z@/api/payments/confirm]"
P2, O2 = "[payments:pay_0902]", "[orders:ord_0902]"
G3, G3r, O3, M3 = "[grants:g_ord_0903]", "[grants:g_ord_0903_retry]", "[orders:ord_0903]", "[mail_events:m_ord_0903@delivered]"
P4, G4, L4 = "[payments:pay_0904]", "[grants:g_ord_0904]", "[server_logs:2026-10-18T18:00:09Z@/api/mail/send]"
O5 = "[orders:ord_0905]"
P6, O6, G6, M6 = "[payments:pay_0906]", "[orders:ord_0906]", "[grants:g_ord_0906]", "[mail_events:m_ord_0906@bounced]"

TRUE = [
    f"The customer paid 24,900 KRW {P1}, but order ord_0901 stayed failed because the confirm step skipped the PSP re-check {L1c}.",
    f"The first card attempt was declined {L1a}, and the retry went through at the payment provider {P1}.",
    f"Payment pay_0902 of 9,900 KRW was PAID {P2}, but order ord_0902 is still pending {O2}.",
    f"Credits were granted twice: {G3} and {G3r}, 60 credits each.",
    f"The order was paid and credited {O3}, and the mail was delivered {M3}.",
    f"The payment went through {P4} and 10 credits were granted {G4}, but the credit email failed with a 500 error {L4}.",
    f"Order ord_0905 is pending {O5}; the customer was never charged.",
    f"The payer paid 24,900 KRW from @example.com {P6}, but the order was saved as @exmaple.com {O6}.",
    f"30 credits were granted to the order address {G6}, and the reward email bounced {M6}.",
    f"결제는 정상 완료되었습니다 {P6}. 안내 메일은 반송되었습니다 {M6}.",
    f"Payment pay_0906 of 24,900 KRW was recorded PAID {P6}; order ord_0906 granted 30 credits {G6}, but the reward email bounced because the order used a different address than the payer {O6} {M6}.",
    f"Payment pay_0902 of 9,900 KRW was PAID {P2}; order ord_0902 remains pending with credited 0 {O2}.",   # model, Zetaris 00:12
    f"Order ord_0905 {O5} has status pending, no payment row, and credited 0.",                                 # model, Zetaris 00:12
    f"Credits have not been granted for order ord_0901 {O1}.",
    f"The order needs to be re-confirmed and credits granted {P1} {O1} {L1c}.",   # a recommendation, written by the model on Zetaris (23:05)
    # written by the model on Zetaris (2026-10-25 01:26), rejected by the version that added time / month checks
    f"Customer ord_0902 paid 9,900\u202fKRW ({P2[1:-1]}) and the PSP webhook PAID arrived ({'server_logs:2026-10-15T20:00:31Z@/api/payments/webhook'}), but order ord_0902 remained pending because the confirm call was never executed, so no credits or email were sent.",
    f"Customer paid 44\u202f900\u202fKRW ({'payments:pay_0903'}) for order ord_0903 ({'orders:ord_0903'}), which is marked paid.",
    f"Two grants ({G3[1:-1]}, {G3r[1:-1]}) each gave 60 credits because the initial confirm timed out and a manual retry repeated the grant.",
    f"The reward email was delivered ({M3[1:-1]}), but the duplicate credit may have caused confusion.",
    f"Order ord_0905 (ref {O5}) has status pending with no payment row, grants, or credited amount.",
    f"Order ord_0904 {O4 if (O4 := '[orders:ord_0904]') else ''} shows a confirmed 9900 KRW payment {P4} and 10 credits granted {G4}, but the credit email failed with a 500 error 'missing API key' {L4}.",
]
FALSE = [
    f"The customer paid 49,900 KRW {P1}.",                                  # wrong amount
    f"The payment failed at the provider {P1}.",                            # payment was PAID
    f"The customer was never charged {P6}.",                                # payment was PAID
    f"The payment was not completed {P2}.",                                 # payment was PAID
    f"결제는 실패했습니다 {P1}.",                                               # KO: payment failed (it was PAID)
    f"Credits were granted twice {G6}.",                                    # one grant only
    f"Order ord_0903 granted 90 credits {G3}.",                             # 60, not 90
    f"10 credits were granted {G6}.",                                       # 30, not 10
    f"The credits were granted successfully {O1}.",                         # ord_0901 not credited
    f"Credits were granted {O5}.",                                          # ord_0905 not credited
    f"No credits were granted {G4}.",                                       # they were
    f"이용권이 두 번 지급되었습니다 {G4}.",                                        # KO: twice (one grant)
    f"The mail was never delivered {M3}.",                                  # it was delivered
    f"The reward email was delivered {M6}.",                                # it bounced
    f"The confirmation mail bounced {M3}.",                                 # delivered, not bounced
    f"안내 메일은 반송되었습니다 {M3}.",                                          # KO: bounced (it was delivered)
    f"Order ord_0999 was paid {P1}.",                                       # unknown order id
    f"Payment pay_0905 was PAID {P1}.",                                     # wrong payment id
    f"Grant g_ord_0904 shows the credits {G6}.",                            # id not in the cited rows
    f"The order was saved under @exmaple.org {O6}.",                        # wrong domain
    f"The payer used @gmail.com {P6}.",                                     # wrong domain
    f"The customer was refunded {P4}.",                                     # nothing is a refund
    f"환불되었습니다 {P6}.",                                                     # KO: refunded
    f"The confirm endpoint failed with a 500 {P2}.",                        # no failure in the cited row
    f"The order total was 12,900 KRW {O2}.",                                # 9900
    f"The order was paid {O5}.",                                            # pending, no PAID payment
    f"The card was declined {P4}.",                                         # PAID
    f"The payment went through {O5}.",                                      # nothing paid
    f"The mail was delivered {L4}.",                                        # a 500 log, no mail event
    f"Duplicate credits were issued {G4}.",                                 # single grant
]

# docs/eval/heldout_*.py: sentence sets written by a separate agent that never saw the checker code
import importlib.util  # noqa: E402
HELD = {}
for f in sorted((ROOT / "docs/eval").glob("heldout_*.py")):
    spec = importlib.util.spec_from_file_location(f.stem, f); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    HELD[f.stem] = (m.WRONG, m.TRUE)

caught = sum(1 for s in FALSE if not _claims_ok(s, ROWS)[0])
rejected = [s for s in TRUE if not _claims_ok(s, ROWS)[0]]
missed = [s for s in FALSE if _claims_ok(s, ROWS)[0]]
print(f"wrong sentences caught: {caught}/{len(FALSE)}")
print(f"true sentences wrongly rejected: {len(rejected)}/{len(TRUE)}")
for s in missed:
    print("  MISSED:", s)
for s in rejected:
    print("  REJECTED:", s, _claims_ok(s, ROWS)[1])
line = (f"| {time.strftime('%Y-%m-%d %H:%M')} | claim check (scripts/claim_eval.py) | wrong sentences caught {caught}/{len(FALSE)}; "
        f"true sentences wrongly rejected {len(rejected)}/{len(TRUE)} | — | — |")
for name, (wrong, true) in HELD.items():
    if not name.endswith("_seen"):
        c = sum(1 for x in wrong if not _claims_ok(x, ROWS)[0]); r = sum(1 for x in true if not _claims_ok(x, ROWS)[0])
        line += f"\n| {time.strftime('%Y-%m-%d %H:%M')} | claim check, unseen set {name} | wrong caught {c}/{len(wrong)}; true wrongly rejected {r}/{len(true)} | — | — |"
if "--record" in sys.argv:
    md = ROOT / "docs/measurements.md"
    md.write_text(md.read_text() + line + "\n")
print(line)
for name, (wrong, true) in HELD.items():
    c = sum(1 for x in wrong if not _claims_ok(x, ROWS)[0]); r = [x for x in true if not _claims_ok(x, ROWS)[0]]
    print(f"{name}: wrong caught {c}/{len(wrong)}, true wrongly rejected {len(r)}/{len(true)}")
    for x in wrong:
        if _claims_ok(x, ROWS)[0]:
            print("  MISSED:", x)
    for x in r:
        print("  REJECTED:", x)
