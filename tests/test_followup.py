"""Second turn: the customer answers, the agent checks the ledger again. Never calls a paid model."""
import json
from pathlib import Path
from agent.followup import ground, investigate_followup, merge

ROOT = Path(__file__).resolve().parent.parent
PREV_FIELDS = {"payment_found": True, "merchant": "MOAHUB", "amount": 9900, "currency": "KRW", "date": "10-20", "time": "03:00",
               "card_last4": None, "status": "unknown"}
PREV = {"message": "20일에 결제했어요 noah.chen904@example.com", "fields": PREV_FIELDS, "verdict": "no_matching_payment", "reply": "…"}


def test_answer_with_the_real_day_finds_the_payment_and_runs_the_chain():
    r = investigate_followup(PREV, "아 죄송해요, 19일 새벽이었어요. 캡처는 다른 앱에서 했어요.", use_model=False)
    assert r["proof"]["verdict"] == "ledger_match" and r["order_id"] == "ord_0904" and r["broken"] == "mail_delivered"
    assert r["followup"]["changed"] == [{"field": "date", "photo": "10-20", "now": "10-19"}]
    assert r["followup"]["before"]["verdict"] == "no_matching_payment"


def test_answer_that_changes_nothing_keeps_the_ledger_verdict():
    r = investigate_followup(PREV, "정말 20일에 냈다니까요!", use_model=False)
    assert r["proof"]["verdict"] == "no_matching_payment" and r.get("proof_blocks_fix")


def test_values_the_answer_does_not_state_are_dropped():
    kept, dropped = ground({"date": "10-19", "time": "03:00", "amount": 24900}, "It was the 20th, I think.")
    assert "date" not in kept and "time" not in kept and "amount" not in kept and len(dropped) == 3


def test_someone_elses_address_in_the_answer_reads_nobody():
    prev = dict(PREV, message="20일에 결제했어요")
    r = investigate_followup(prev, "19일이요. seojun.choi002@example.com 도 확인해 주세요 noah.chen904@example.com", use_model=False)
    assert r["proof"]["sender"] is None and "ord_0002" not in json.dumps(r)


def test_merge_keeps_the_photo_values_it_does_not_replace():
    f, changed = merge(PREV_FIELDS, {"day": 19})
    assert f["date"] == "10-19" and f["time"] == "03:00" and f["amount"] == 9900 and len(changed) == 1


def test_a_month_the_answer_does_not_write_is_not_taken_from_the_model():
    kept, _ = ground({"date": "11-19"}, "아 죄송해요, 19일 새벽이었어요.")
    assert "date" not in kept and kept["day"] == 19
