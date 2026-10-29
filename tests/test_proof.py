"""Screenshot proof (agent/proof.py), the per-job model routing and cost, and the escalation rule. No network and no
OCR (OCR_DISABLE=1): a scripted client stands in for the vision, intake and reply models."""
import base64, importlib, io, json
from types import SimpleNamespace
import pytest

from agent.llm import CallLog, TracedClient, cost_usd, model_for
from agent.proof import check_fields, decide, prepare_image, template_reply, _ACCUSE


@pytest.fixture(autouse=True)
def _no_ocr(monkeypatch):
    monkeypatch.setenv("OCR_DISABLE", "1")
    monkeypatch.setenv("AGENT_LOOP", "0")


def _png(w=300, h=600, exif=False) -> bytes:
    from PIL import Image
    im = Image.new("RGB", (w, h), "white")
    buf = io.BytesIO()
    if exif:
        ex = Image.Exif(); ex[0x010F] = "SecretPhoneMaker"
        im.save(buf, "JPEG", exif=ex.tobytes())
    else:
        im.save(buf, "PNG")
    return buf.getvalue()


def _screen(**kw):
    base = {"payment_found": True, "merchant": "MOAHUB", "amount": 24900, "currency": "KRW", "amount_text": "24,900원",
            "date": "2026-10-13", "time": "21:00", "datetime_text": "2026.10.13 21:00", "card_last4": "4242", "status": "approved",
            "status_text": "승인", "screen_language": "ko", "ignored_numbers": [{"text": "152,300원", "what": "balance"}], "legibility": "clear"}
    return {**base, **kw}


def _payments(email):
    from agent.sql_backend import DuckDBBackend
    from agent.tools import Tools
    return Tools(DuckDBBackend()).find_payments(email)


def test_prepare_image_strips_metadata_and_downscales():
    jpeg, info = prepare_image(_png(3000, 6000, exif=True))
    from PIL import Image
    im = Image.open(io.BytesIO(jpeg))
    assert max(im.size) <= 1600 and info["original_size"] == [3000, 6000]
    assert b"SecretPhoneMaker" not in jpeg and not im.getexif()
    with pytest.raises(ValueError):
        prepare_image(b"not an image")
    with pytest.raises(ValueError):
        prepare_image(b"")


def test_true_screenshot_matches_the_ledger():
    f = check_fields(_screen())
    d = decide(f, _payments("hana.lee901@example.com"))      # pay_0901: 24,900 at 12:00:40Z = 21:00 KST, card 4242
    assert d["verdict"] == "ledger_match" and d["matched"] == "payments:pay_0901"
    assert all(r["result"] == "match" for r in d["comparison"])


def test_edited_amount_or_time_is_not_in_the_ledger():
    pays = _payments("hana.lee901@example.com")
    d = decide(check_fields(_screen(amount=44900, amount_text="44,900원")), pays)
    assert d["verdict"] == "no_matching_payment" and d["matched"] is None
    assert [r["result"] for r in d["comparison"] if r["field"] == "amount"] == ["differs"]
    assert decide(check_fields(_screen(time="20:00")), pays)["verdict"] == "no_matching_payment"
    assert decide(check_fields(_screen(date="2026-10-12")), pays)["verdict"] == "no_matching_payment"
    assert decide(check_fields(_screen(time="21:08")), pays)["verdict"] == "ledger_match"   # within ±10 min
    assert decide(check_fields(_screen(card_last4="9999")), pays)["verdict"] == "no_matching_payment"


def test_unpaid_screen_and_unreadable_screen():
    assert decide(check_fields(_screen(status="pending", status_text="결제 대기")), _payments("emma.song905@example.com"))["verdict"] == "not_paid"
    assert decide(check_fields(_screen(payment_found=False, amount=None, amount_text=None)), [])["verdict"] == "unread"
    d = decide(check_fields(_screen(date="10-13")), _payments("hana.lee901@example.com"))
    assert d["verdict"] == "ledger_match" and any("no year" in n for n in d["notes"])


def test_check_fields_drops_values_that_do_not_hold_together():
    f = check_fields(_screen(amount=44900, amount_text="24,900원", card_last4="42a2", time="25:00"))
    assert f["amount"] is None and f["card_last4"] is None and f["time"] is None
    assert {d["field"] for d in f["dropped"]} == {"amount", "card_last4", "time"}


def test_template_reply_never_accuses():
    f = check_fields(_screen(amount=44900, amount_text="44,900원"))
    for lang in ("en", "ko", "ja"):
        t = template_reply(f, {}, {"amount": 24900, "created_at": "2026-10-13T12:00:40Z", "status": "PAID"}, lang)
        assert "44,900" in t and not _ACCUSE.search(t)
    assert not _ACCUSE.search("We will check your credits")   # 'credit' is not 'edit'


class _Scripted:
    """Vision / intake / explain / reply stand-ins. Records every request."""
    def __init__(self, screen: dict, reply: str = "", intake: dict | None = None):
        self.sent, self.screen, self.reply, self.intake = [], screen, reply, intake
        self.chat = SimpleNamespace(completions=self)

    def create(self, model=None, messages=None, **kw):
        self.sent.append({"model": model, "messages": messages, "kw": {k: v for k, v in kw.items() if k != "messages"}})
        sysm = messages[0]["content"]
        if "You read ONE photo" in sysm:
            body = self.screen
        elif "You write a short reply FROM" in sysm:
            body = {"customer_reply": self.reply}
        elif "You read one customer message" in sysm:
            body = self.intake or {"sender": "EMAIL_1", "complaint": "not_received", "plan": []}
        else:
            body = {"explanation": "", "customer_reply": "", "fix_action": ""}
        msg = SimpleNamespace(content=json.dumps(body), model_extra={})
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)], model=model, usage=SimpleNamespace(prompt_tokens=1000, completion_tokens=100))


def _with(monkeypatch, s):
    monkeypatch.setattr("agent.investigator._client", lambda: (TracedClient(s, CallLog(), "Nebius Token Factory"), model_for("explain")))


def test_proof_pipeline_routes_jobs_to_different_models(monkeypatch):
    s = _Scripted(_screen())
    _with(monkeypatch, s)
    from agent.proof import investigate_proof
    r = investigate_proof(_png(), "돈 냈어요 이거 보세요 hana.lee901@example.com")
    assert r["proof"]["verdict"] == "ledger_match"
    assert r["order_id"] == "ord_0901" and r["broken"] == "order_created"      # the usual chain for the matched order
    roles = [c["role"] for c in r["model_calls"]]
    assert roles[0] == "vision" and "explain" in roles
    vis = s.sent[0]
    assert vis["model"] == "nvidia/Nemotron-3.5-Super-VL"
    assert vis["kw"]["response_format"]["type"] == "json_schema"
    assert vis["messages"][1]["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert r["model_calls"][0]["usd"] == cost_usd("nvidia/Nemotron-3.5-Super-VL", 1000, 100)
    assert "hana.lee901@" not in json.dumps([x["messages"][1:] for x in s.sent[1:]])   # addresses masked for text models


def test_doctored_screenshot_gets_a_polite_request_not_a_fix(monkeypatch):
    s = _Scripted(_screen(amount=44900, amount_text="44,900원"), reply="이 캡처는 편집된 것 같습니다.")   # an accusing reply
    _with(monkeypatch, s)
    from agent.proof import investigate_proof
    r = investigate_proof(_png(), "돈 냈어요 hana.lee901@example.com")
    assert r["proof"]["verdict"] == "no_matching_payment"
    assert r["proof"]["reply"]["source"] == "template" and "suggests" in r["proof"]["reply"]["why"]
    assert "44,900" in r["customer_reply"] and r["proof_blocks_fix"]
    assert [c["role"] for c in r["model_calls"]] == ["vision", "reply"]       # no planner/explain on someone else's story


def test_vision_endpoint_refusing_json_schema_gets_one_plain_try(monkeypatch):
    class Refuses(_Scripted):
        def create(self, model=None, messages=None, **kw):
            if "response_format" in kw:
                raise RuntimeError("400 BadRequest: response_format json_schema not supported")
            return super().create(model=model, messages=messages, **kw)
    from agent.proof import read_screen
    c = TracedClient(Refuses(_screen()), CallLog(), "x")
    r = read_screen(c, prepare_image(_png())[0])
    assert r["ok"] and r["json_mode"].startswith("off") and len(c.log) == 2 and not c.log[0]["ok"]


def test_intake_escalates_only_when_unsure(monkeypatch):
    from agent.intake import read_with_routing
    sure = _Scripted({}, intake={"sender": "EMAIL_1", "complaint": "not_received", "plan": []})
    c = TracedClient(sure, CallLog(), "x")
    r = read_with_routing(c, "paid 24,900 hana.lee901@example.com")
    assert not r["routing"]["escalated"] and [x["role"] for x in c.log] == ["intake"]
    assert sure.sent[0]["model"] == "nvidia/Nemotron-3_5-Lightning"
    unsure = _Scripted({}, intake={"sender": None, "complaint": "other", "plan": []})
    c = TracedClient(unsure, CallLog(), "x")
    r = read_with_routing(c, "my wife a@example.org, me b@example.com, paid")
    assert r["routing"]["escalated"] and [x["role"] for x in c.log] == ["intake", "escalate"]
    assert unsure.sent[1]["model"] == "nvidia/Nemotron-3-Ultra-550b-a55b"


def test_vision_model_never_falls_back_to_a_text_model(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "nvidia/nemotron-3-super-120b-a12b")
    assert model_for("vision") == "nvidia/Nemotron-3.5-Super-VL"
    monkeypatch.setenv("LLM_VISION_MODEL", "nvidia/other-vl")
    assert model_for("vision") == "nvidia/other-vl"


# ---------------- the endpoint ----------------

@pytest.fixture
def public_app(monkeypatch):
    monkeypatch.setenv("DEMO_PUBLIC", "1")
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    monkeypatch.delenv("LLM_FAKE", raising=False)
    monkeypatch.setenv("DEMO_LIVE_PER_IP_HOUR", "2")
    import app.main as m
    m = importlib.reload(m)
    from fastapi.testclient import TestClient
    yield m, TestClient
    monkeypatch.setenv("DEMO_PUBLIC", "0")
    importlib.reload(m)


def test_proof_endpoint_public_mode_limits_and_rejects_bad_input(public_app, monkeypatch):
    m, TC = public_app
    monkeypatch.setattr("agent.proof.read_fields", lambda jpeg, client, ocr: (check_fields(_screen()), {"ok": True, "reader": "test"}))
    c = TC(m.app)
    img = "data:image/png;base64," + base64.b64encode(_png()).decode()
    body = {"image": img, "message": "paid hana.lee901@example.com"}
    rs = [c.post("/api/proof", json=body).json() for _ in range(3)]
    assert rs[0]["proof"]["verdict"] == "ledger_match" and "limited" not in rs[0]
    assert rs[2]["limited"] and rs[2]["proof"]["verdict"] == "ledger_match"   # past the limit the ledger still answers
    assert c.post("/api/proof", json={"image": "!!!", "message": "x"}).status_code == 400
    bad = c.post("/api/proof", json={"image": base64.b64encode(b"hello").decode(), "message": "x"}).json()
    assert bad["ok"] is False and "can't be used" in bad["headline"]
    assert c.post("/api/proof", json={"image": "A" * 12_000_001}).status_code == 422


def test_thinking_toggle_per_job_and_length_is_reported(monkeypatch):
    monkeypatch.setenv("LLM_THINKING_VISION", "off")
    s = _Scripted(_screen())
    c = TracedClient(s, CallLog(), "x")
    from agent.proof import read_screen
    assert read_screen(c, prepare_image(_png())[0])["ok"]
    assert s.sent[0]["kw"]["extra_body"]["chat_template_kwargs"] == {"enable_thinking": False}

    class Truncated(_Scripted):   # reasoning used every token: empty content, finish_reason=length
        def create(self, model=None, messages=None, **kw):
            msg = SimpleNamespace(content="", model_extra={"reasoning_content": "The user wants..."})
            return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason="length")], model=model,
                                   usage=SimpleNamespace(prompt_tokens=1652, completion_tokens=1200))
    r = read_screen(TracedClient(Truncated(_screen()), CallLog(), "x"), prepare_image(_png())[0])
    assert not r["ok"] and "all its tokens" in r["error"]


def test_ocr_text_only_mode_sends_no_image():
    from agent.proof import read_screen
    s = _Scripted(_screen())
    r = read_screen(TracedClient(s, CallLog(), "x"), None, ocr_text="모아허브(MOAHUB)\n결제금액 24,900원")
    assert r["ok"] and isinstance(s.sent[0]["messages"][1]["content"], str) and "OCR text" in s.sent[0]["messages"][0]["content"]


def test_check_fields_fills_empty_date_time_from_its_own_quote_only():
    f = check_fields(_screen(date=None, time=None, datetime_text="10/20 03:00"))
    assert f["date"] == "10-20" and f["time"] == "03:00"
    f = check_fields(_screen(date=None, time=None, datetime_text="오후 3:05"))   # 12-hour quote: not guessed
    assert f["time"] is None
