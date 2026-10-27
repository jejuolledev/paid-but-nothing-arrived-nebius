"""Build the frozen screenshot eval set (heldout 16 + dev 6) deterministically.

usage: .venv/bin/python scripts/eval_screens/build.py

Reads only data/out/payments.csv and data/out/orders.csv (the seeded ledger rows for
ids 0901-0906). Renders fictional payment-app screens with headless Chromium, makes the
crude edits for doctored images, applies phone-photo distortions, and writes
docs/eval/screens/{heldout,dev}/[clean/]*.png, manifest.jsonl and contact sheets.
"""
from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from string import Template

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from distort import contact_sheet, crude_paste, photo  # noqa: E402

OUT = ROOT / "docs/eval/screens"
WORK = ROOT / "scripts/eval_screens/_work"   # intermediate html/png, not committed
NODE = "node"
KST = timedelta(hours=9)
JPY_RATE = 0.1092
WD_KO = "월화수목금토일"
WD_JA = "月火水木金土日"

# ------------------------------------------------------------------ ledger
def load_ledger():
    pays = {r["payment_id"]: r for r in csv.DictReader(open(ROOT / "data/out/payments.csv"))}
    orders = {r["order_id"]: r for r in csv.DictReader(open(ROOT / "data/out/orders.csv"))}
    return pays, orders


PAYS, ORDERS = load_ledger()


def utc(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")


CASES = {
    1: dict(pay="pay_0901", email="hana.lee901@example.com", mask_ko="이*나"),
    2: dict(pay="pay_0902", email="jun.park902@example.com", mask_ko="박*준"),
    3: dict(pay="pay_0903", email="sora.kim903@example.com", mask_ko="김*라"),
    4: dict(pay="pay_0904", email="noah.chen904@example.com", mask_ko="N**H CHEN"),
    5: dict(pay=None, email="emma.song905@example.com", mask_ko="송*마", order="ord_0905"),
    6: dict(pay="pay_0906", email="liam.patel906@example.com", mask_ko="L**M PATEL"),
}


def truth(case):
    c = CASES[case]
    if c["pay"]:
        p = PAYS[c["pay"]]
        return dict(amount=int(p["amount"]), local=utc(p["created_at"]) + KST, last4=p["card_last4"], pay=c["pay"])
    o = ORDERS[c["order"]]
    return dict(amount=int(o["amount"]), local=utc(o["created_at"]) + KST, last4=None, pay=None)


# ------------------------------------------------------------------ specs
# edit: amount -> new KRW amount; time -> "HH:MM"; date -> "YYYY-MM-DD"; style e1..e4;
# recipe: crude paste parameters (see distort.crude_paste)
SPECS = [
    # ---- heldout, true / unpaid
    dict(id="s01", split="heldout", style="A_bank_detail", lang="ko", kind="true", case=1, dark=False,
         dist=["perspective", "glare", "jpeg"], s=0.4, diff="medium",
         msg="결제했는데 크레딧이 안 들어왔어요. 은행 앱 캡처 보냅니다. hana.lee901@example.com"),
    dict(id="s02", split="heldout", style="B_card_push_list", lang="ko", kind="true", case=2, dark=False,
         dist=["moire", "perspective", "noise", "jpeg"], s=0.5, diff="medium",
         msg="돈 냈어요 이거 보세요 jun.park902@example.com"),
    dict(id="s03", split="heldout", style="E_jp_card_detail", lang="ja", kind="true", case=3, dark=False,
         dist=["rotate", "jpeg"], s=0.2, diff="easy",
         msg="カード明細のスクショです。何か二重になっていませんか？ sora.kim903@example.com"),
    dict(id="s04", split="heldout", style="D_sms_approval", lang="ko", kind="true", case=4, dark=True,
         dist=["perspective", "moire", "glare", "noise", "jpeg"], s=0.85, diff="hard",
         msg="결제됐다고 문자는 왔는데 메일이 하나도 안 와요 noah.chen904@example.com"),
    dict(id="s05", split="heldout", style="F_jp_pay_history", lang="ja", kind="true", case=6, dark=False,
         dist=["crop", "perspective", "jpeg"], s=0.4, diff="medium",
         msg="支払いは済んでいます。履歴の画面を送ります。liam.patel906@example.com"),
    dict(id="s06", split="heldout", style="C_easypay_receipt", lang="ko", kind="unpaid", case=5, dark=False,
         dist=["perspective", "glare", "jpeg"], s=0.3, diff="easy",
         msg="결제했는데 왜 크레딧이 없죠? 화면 캡처 첨부해요. emma.song905@example.com"),
    dict(id="s07", split="heldout", style="E_jp_card_detail", lang="ja", kind="true", case=4, dark=True,
         dist=["perspective", "motion_blur", "noise", "downscale", "jpeg"], s=0.75, diff="hard",
         msg="決済した明細です。確認メールが届きません。noah.chen904@example.com"),
    dict(id="s08", split="heldout", style="C_easypay_receipt", lang="ko", kind="true", case=1, dark=False,
         dist=["rotate", "dim", "noise", "jpeg"], s=0.5, diff="medium",
         msg="도토리페이로 결제 완료됐다고 나와요!! 확인 부탁해요 hana.lee901@example.com"),
    # ---- heldout, doctored
    dict(id="s09", split="heldout", style="A_bank_detail", lang="ko", kind="doctored", case=2, dark=False,
         edit=dict(amount=44900), estyle="e1", recipe=dict(pad=5, tone=3, jpeg_q=55),
         dist=["perspective", "jpeg"], s=0.3, diff="easy",
         msg="44,900원 결제했는데 패밀리 60 안 들어왔어요. 캡처 확인하세요 jun.park902@example.com"),
    dict(id="s10", split="heldout", style="B_card_push_list", lang="ko", kind="doctored", case=1, dark=True,
         edit=dict(time="20:00"), estyle="e2", recipe=dict(pad=4, tone=-4, jpeg_q=None, region_jpeg_q=45),
         dist=["moire", "rotate", "jpeg"], s=0.5, diff="medium",
         msg="밤 8시에 결제한 거 아직 처리 안 됐어요 hana.lee901@example.com"),
    dict(id="s11", split="heldout", style="D_sms_approval", lang="ko", kind="doctored", case=3, dark=False,
         edit=dict(date="2026-10-16"), estyle="e3", recipe=dict(pad=3, tone=5, alias=True),
         dist=["perspective", "blur", "glare", "jpeg"], s=0.7, diff="hard",
         msg="16일에 결제한 건데 크레딧 확인 좀 해주세요 sora.kim903@example.com"),
    dict(id="s12", split="heldout", style="E_jp_card_detail", lang="ja", kind="doctored", case=6, dark=False,
         edit=dict(amount=44900), estyle="e4", recipe=dict(pad=4, tone=-3, jpeg_q=40),
         dist=["perspective", "noise", "jpeg"], s=0.4, diff="medium",
         msg="44,900ウォン払いました。60クレジットが付いていません。liam.patel906@example.com"),
    dict(id="s13", split="heldout", style="F_jp_pay_history", lang="ja", kind="doctored", case=2, dark=True,
         edit=dict(time="04:12"), estyle="e1", recipe=dict(pad=4, tone=6, jpeg_q=50),
         dist=["crop", "moire", "perspective", "jpeg"], s=0.8, diff="hard",
         msg="朝4時過ぎに支払いました。画面を見てください。jun.park902@example.com"),
    dict(id="s14", split="heldout", style="C_easypay_receipt", lang="ko", kind="doctored", case=4, dark=False,
         edit=dict(amount=24900), estyle="e2", recipe=dict(pad=6, tone=-5, jpeg_q=60, dx=1),
         dist=["rotate", "glare", "jpeg"], s=0.4, diff="medium",
         msg="24,900원 냈는데 30크레딧 들어온 거 맞나요? 메일이 없어서요 noah.chen904@example.com"),
    dict(id="s15", split="heldout", style="A_bank_detail", lang="ko", kind="doctored", case=4, dark=False,
         edit=dict(time="02:30"), estyle="e3", recipe=dict(pad=4, tone=4, jpeg_q=45, region_jpeg_q=50),
         dist=["moire", "perspective", "downscale", "noise", "jpeg"], s=0.85, diff="hard",
         msg="새벽 2시 반에 결제했어요. 확인 부탁드립니다 noah.chen904@example.com"),
    dict(id="s16", split="heldout", style="B_card_push_list", lang="ko", kind="doctored", case=6, dark=False,
         edit=dict(amount=44900, time="01:40"), estyle="e4", recipe=dict(pad=3, tone=-2, jpeg_q=65),
         dist=["perspective", "jpeg"], s=0.2, diff="easy",
         msg="패밀리팩 결제했는데 아무것도 안 왔어요 liam.patel906@example.com"),
    # ---- dev
    dict(id="d01", split="dev", style="D_sms_approval", lang="ko", kind="true", case=2, dark=False,
         dist=["perspective", "glare", "jpeg"], s=0.4, diff="medium",
         msg="결제 문자 캡처입니다. 크레딧 언제 들어와요? jun.park902@example.com"),
    dict(id="d02", split="dev", style="F_jp_pay_history", lang="ja", kind="true", case=3, dark=False,
         dist=["rotate", "noise", "jpeg"], s=0.4, diff="easy",
         msg="支払い履歴です。sora.kim903@example.com"),
    dict(id="d03", split="dev", style="A_bank_detail", lang="ko", kind="true", case=6, dark=True,
         dist=["moire", "perspective", "jpeg"], s=0.6, diff="medium",
         msg="통장에서 빠져나갔어요 liam.patel906@example.com"),
    dict(id="d04", split="dev", style="F_jp_pay_history", lang="ja", kind="unpaid", case=5, dark=False,
         dist=["perspective", "jpeg"], s=0.3, diff="easy",
         msg="払ったはずなのにクレジットがありません。emma.song905@example.com"),
    dict(id="d05", split="dev", style="B_card_push_list", lang="ko", kind="doctored", case=4, dark=False,
         edit=dict(date="2026-10-20"), estyle="e1", recipe=dict(pad=4, tone=4, jpeg_q=50),
         dist=["perspective", "blur", "jpeg"], s=0.5, diff="medium",
         msg="20일에 결제했어요 noah.chen904@example.com"),
    dict(id="d06", split="dev", style="E_jp_card_detail", lang="ja", kind="doctored", case=1, dark=False,
         edit=dict(time="22:00"), estyle="e2", recipe=dict(pad=4, tone=-4, jpeg_q=45),
         dist=["moire", "jpeg"], s=0.5, diff="medium",
         msg="夜10時に支払いました。hana.lee901@example.com"),
]

KO_SHOPS = ["한빛편의점", "동네마트 정자점", "카페 오월", "온누리약국", "해오름주유소", "버스·지하철", "골목분식", "책방 들꽃"]
JA_SHOPS = ["コンビニ ひまわり", "カフェ こもれび", "ドラッグ あおば", "書店 ことのは", "ベーカリー こむぎ", "交通IC チャージ"]


def won(n):
    return f"{n:,}"


def apply_edit(local, amount, edit):
    if not edit:
        return local, amount
    if "amount" in edit:
        amount = edit["amount"]
    if "time" in edit:
        hh, mm = map(int, edit["time"].split(":"))
        local = local.replace(hour=hh, minute=mm)
    if "date" in edit:
        y, m, d = map(int, edit["date"].split("-"))
        local = local.replace(year=y, month=m, day=d)
    return local, amount


def sb_time(rng, avoid: datetime, ja=False):
    while True:
        h, m = int(rng.integers(0, 24)), int(rng.integers(0, 60))
        if (h, m) != (avoid.hour, avoid.minute) and abs(h - avoid.hour) >= 2:
            return f"{h}:{m:02d}"


def other_time(rng, avoid):
    while True:
        h, m = int(rng.integers(7, 24)), int(rng.integers(0, 60))
        if abs(h - avoid.hour) >= 2:
            return h, m


# ------------------------------------------------------------------ fill
def fill(spec, local, amount, last4, rng, edited_fields=()):
    """Return (html_vars, distractors). edited_fields: set of span ids to mark edited."""
    st = spec["style"]
    dark = spec["dark"]
    estyle = spec.get("estyle", "")
    D = []
    v = dict(bodyclass="dark" if dark else "", batt_w=f"{int(rng.integers(30, 95))}%")
    v["sb_time"] = sb_time(rng, local)
    D.append(dict(kind="status_bar_clock", text=v["sb_time"]))
    v["amount_fmt"] = won(amount)
    v["last4"] = last4 or ""
    v["date_dot"] = local.strftime("%Y.%m.%d")
    v["date_slash"] = local.strftime("%Y/%m/%d")
    v["date_md"] = local.strftime("%m/%d")
    v["time_hm"] = local.strftime("%H:%M")
    v["time_hms"] = local.strftime("%H:%M:%S")

    def ef(span_id, text):
        cls = f"ef edited {estyle}" if span_id in edited_fields else "ef"
        return f'<span class="{cls}" id="{span_id}">{text}</span>'

    if st == "A_bank_detail":
        v["label"] = "출금"
        v["status_text"] = "정상 처리"
        bal = int(rng.integers(40, 900)) * 100 + 300
        v["balance"] = won(bal)
        D.append(dict(kind="balance", text=f"{won(bal)}원"))
        pts = int(amount * 0.005)
        v["points"] = won(pts)
        D.append(dict(kind="points", text=f"+{won(pts)} P"))
        v["ad_amount"] = won(int(rng.choice([100000, 300000, 500000])))
        D.append(dict(kind="ad_banner", text=f"연 3.8% · 매달 {v['ad_amount']}원 · 최대 1,000,000원"))
        lis = []
        for _ in range(3):
            h, m = other_time(rng, local)
            amt = int(rng.integers(12, 680)) * 100
            shop = KO_SHOPS[int(rng.integers(0, len(KO_SHOPS)))]
            lis.append(f'<div class="li"><span>{h:02d}:{m:02d} {shop}</span><span>-{won(amt)}원</span></div>')
            D.append(dict(kind="other_transaction", text=f"{h:02d}:{m:02d} {shop} -{won(amt)}원"))
        v["others"] = "\n".join(lis)
    elif st == "B_card_push_list":
        v["masked_name"] = CASES[spec["case"]]["mask_ko"]
        v["ago"] = f"{int(rng.integers(3, 9))}일 전"
        cum = int(rng.integers(300, 4000)) * 1000 + int(rng.integers(0, 10)) * 100
        v["cumulative"] = won(cum)
        D.append(dict(kind="cumulative_spend", text=f"누적 {won(cum)}원"))
        def note(body, ago, ad=False):
            ic = "광" if ad else "솔"
            return (f'<div class="n{" ad" if ad else ""}"><div class="h"><span class="ic">{ic}</span>솔카드'
                    f'<span class="ago">{ago}</span></div><div class="b">{body}</div></div>')
        h, m = other_time(rng, local)
        a1 = int(rng.integers(15, 99)) * 100
        shop = KO_SHOPS[int(rng.integers(0, 4))]
        d_prev = (local - timedelta(days=1)).strftime("%m/%d")
        bf = note(f"<b>솔카드({last4}) 승인</b>\n{v['masked_name']}님\n{won(a1)}원 일시불\n{local.strftime('%m/%d')} {h:02d}:{m:02d} {shop}", "방금")
        D.append(dict(kind="other_transaction", text=f"{won(a1)}원 {h:02d}:{m:02d} {shop}"))
        bf += note("<b>[솔카드] 이번 주말 캐시백</b>\n5만원 이상 결제 시 최대 20,000원 캐시백 (~10/31)", "1일 전", ad=True)
        D.append(dict(kind="ad_banner", text="최대 20,000원 캐시백"))
        h2, m2 = other_time(rng, local)
        inst = int(rng.choice([89000, 129000, 239000]))
        af = note(f"<b>솔카드({last4}) 승인</b>\n{v['masked_name']}님\n{won(inst)}원 할부 3개월\n{d_prev} {h2:02d}:{m2:02d} 바른가구", f"{int(v['ago'][0]) + 1}일 전")
        D.append(dict(kind="installment", text=f"{won(inst)}원 할부 3개월 {d_prev} {h2:02d}:{m2:02d}"))
        due = int(rng.integers(150, 900)) * 1000 + 300
        af += note(f"<b>[솔카드] 결제 예정 금액 안내</b>\n10/25 결제 예정 {won(due)}원\n포인트 {int(rng.integers(100, 3000))}P 사용 가능", "9일 전")
        D.append(dict(kind="statement_due", text=f"결제 예정 {won(due)}원"))
        v["before"], v["after"] = bf, af
    elif st == "C_easypay_receipt":
        if spec["kind"] == "unpaid":
            cards = ["가람카드 ****3391", "솔카드 ****7720"]
            money = int(rng.integers(5, 300)) * 100
            v["body"] = f"""
<div class="st" style="--stc:var(--warn)"><div class="ic">!</div><div class="t">결제 대기</div>
<div class="s">결제수단을 선택하면 결제가 진행돼요</div></div>
<div class="amt num">{won(amount)}원</div>
<div class="card">
<div class="row"><span>가맹점</span><span>모아허브(MOAHUB)</span></div>
<div class="row"><span>상품</span><span>스탠다드 30 크레딧</span></div>
<div class="row"><span>주문일시</span><span class="num">{v['date_dot']} {v['time_hm']}</span></div>
<div class="row"><span>결제수단</span><span>선택 안 함</span></div>
<div class="row"><span>상태</span><span style="color:var(--warn)">결제 대기 · 미승인</span></div>
</div>
<div class="sel">
<div class="opt"><span>도토리머니</span><span class="num">잔액 {won(money)}원</span></div>
<div class="opt"><span>{cards[0]}</span><span>○</span></div>
<div class="opt"><span>{cards[1]}</span><span>○</span></div>
</div>
<div class="btn">{won(amount)}원 결제하기</div>"""
            D += [dict(kind="saved_card", text=cards[0]), dict(kind="saved_card", text=cards[1]),
                  dict(kind="balance", text=f"도토리머니 잔액 {won(money)}원"),
                  dict(kind="pay_button", text=f"{won(amount)}원 결제하기")]
        else:
            truth_amt = truth(spec["case"])["amount"]
            pts = int(amount * 0.01)
            money = int(rng.integers(5, 300)) * 100
            approval = f"{int(rng.integers(10000000, 99999999))}"
            v["body"] = f"""
<div class="st" style="--stc:var(--ok)"><div class="ic">✓</div><div class="t">결제 완료</div>
<div class="s">모아허브(MOAHUB)</div></div>
<div class="amt num">{ef('t-amount', won(amount) + '원')}</div>
<div class="card">
<div class="row"><span>상품</span><span>{ {9900: '라이트 10', 24900: '스탠다드 30', 44900: '패밀리 60'}[truth_amt] } 크레딧</span></div>
<div class="row"><span>주문금액</span><span class="num">{won(truth_amt)}원</span></div>
<div class="row"><span>결제수단</span><span class="num">가람카드 ****{last4} · 일시불</span></div>
<div class="row"><span>결제일시</span><span class="num">{ef('t-dt', v['date_dot'] + ' ' + v['time_hm'])}</span></div>
<div class="row"><span>승인번호</span><span class="num">{approval}</span></div>
<div class="row"><span>도토리포인트</span><span class="num">+{won(pts)}P 적립</span></div>
<div class="row"><span>도토리머니 잔액</span><span class="num">{won(money)}원</span></div>
</div>
<div class="bn"><b>친구 초대하고 3,000원 받기</b>초대한 친구가 첫 결제하면 둘 다 3,000P</div>"""
            D += [dict(kind="order_amount_row", text=f"주문금액 {won(truth_amt)}원"),
                  dict(kind="approval_number", text=approval),
                  dict(kind="points", text=f"+{won(pts)}P"),
                  dict(kind="balance", text=f"도토리머니 잔액 {won(money)}원"),
                  dict(kind="ad_banner", text="3,000원 / 3,000P")]
    elif st == "D_sms_approval":
        v["masked_name"] = CASES[spec["case"]]["mask_ko"]
        v["unread"] = str(int(rng.integers(2, 40)))
        cum = int(rng.integers(300, 4000)) * 1000 + int(rng.integers(0, 10)) * 100
        v["cumulative"] = won(cum)
        D.append(dict(kind="cumulative_spend", text=f"누적{won(cum)}원"))
        t = truth(spec["case"])["local"]  # day label + bubble time are NOT edited by a crude editor
        v["day_label"] = f"{t.year}년 {t.month}월 {t.day}일 {WD_KO[t.weekday()]}요일"
        ap = "오전" if t.hour < 12 else "오후"
        v["bubble_time"] = f"{ap} {t.hour % 12 or 12}:{t.minute:02d}"
        prev = t - timedelta(days=1)
        h, m = other_time(rng, t)
        a1 = int(rng.integers(15, 450)) * 100
        shop = KO_SHOPS[int(rng.integers(0, len(KO_SHOPS)))]
        bf = (f'<div class="day">{prev.year}년 {prev.month}월 {prev.day}일 {WD_KO[prev.weekday()]}요일</div>'
              f'<div class="bb">[Web발신]\n가람카드({last4})승인\n{v["masked_name"]}님\n{won(a1)}원 일시불\n'
              f'{prev.strftime("%m/%d")} {h:02d}:{m:02d}\n{shop}\n누적{won(cum - amount - a1 + 0)}원</div>'
              f'<div class="tm">{"오전" if h < 12 else "오후"} {h % 12 or 12}:{m:02d}</div>')
        D.append(dict(kind="other_transaction", text=f"{won(a1)}원 {prev.strftime('%m/%d')} {h:02d}:{m:02d} {shop}"))
        af = ('<div class="bb">(광고)[가람카드] 10월 한정 2~6개월 무이자 할부! 5만원 이상 결제 시 '
              '최대 30,000원 청구할인 무료수신거부 080-000-0000</div><div class="tm">오후 1:05</div>')
        D.append(dict(kind="ad_sms", text="2~6개월 무이자 / 최대 30,000원"))
        v["before"], v["after"] = bf, af
    elif st == "E_jp_card_detail":
        tr = truth(spec["case"])
        jpy = round(tr["amount"] * JPY_RATE)  # crude editors leave the yen conversion untouched
        v["jpy_fmt"] = won(jpy)
        v["rate"] = f"{JPY_RATE:.4f}"
        D.append(dict(kind="jpy_conversion", text=f"{won(jpy)}円"))
        D.append(dict(kind="fx_rate", text=f"1 KRW = {JPY_RATE:.4f} 円"))
        v["status_text"] = "確定"
        v["points"] = won(int(rng.integers(20, 3000)))
        D.append(dict(kind="points", text=f"{v['points']} pt"))
        v["pay_due"] = "2026/11/26"
        v["next_due"] = "11/26"
        na = int(rng.integers(8000, 90000))
        v["next_amount"] = won(na)
        D.append(dict(kind="statement_due", text=f"次回お支払い金額 {won(na)}円"))
        av = int(rng.integers(50, 500)) * 1000
        v["available"] = won(av)
        D.append(dict(kind="available_credit", text=f"ご利用可能額 {won(av)}円"))
        v["ad_pt"] = won(int(rng.choice([500, 1000, 2000])))
        D.append(dict(kind="ad_banner", text=f"{v['ad_pt']} pt プレゼント"))
    elif st == "F_jp_pay_history":
        bal = int(rng.integers(3, 300)) * 10
        v["balance"] = won(bal)
        D.append(dict(kind="balance", text=f"残高 {won(bal)}円"))
        v["promo_pt"] = won(int(rng.integers(10, 400)))
        D.append(dict(kind="points", text=f"{v['promo_pt']} pt"))
        tr = truth(spec["case"])
        jpy = round(tr["amount"] * JPY_RATE)
        def dh(d):
            return f'<div class="dh">{d.month}月{d.day}日（{WD_JA[d.weekday()]}）</div>'
        def item(icon, title, sub, amt, sub2=""):
            s2 = f'<div class="s2">{sub2}</div>' if sub2 else ""
            return (f'<div class="it"><div class="ic">{icon}</div><div class="m"><div class="t">{title}</div>'
                    f'<div class="s">{sub}</div></div><div class="a num">{amt}{s2}</div></div>')
        rows = [dh(local)]
        h, m = other_time(rng, local)
        a1 = int(rng.integers(12, 160)) * 10
        shop = JA_SHOPS[int(rng.integers(0, len(JA_SHOPS)))]
        later = (h, m) > (local.hour, local.minute)
        o1 = item("🛒", shop, f"{h:02d}:{m:02d} ・ 残高払い", f"-{won(a1)}円")
        D.append(dict(kind="other_transaction", text=f"{shop} {h:02d}:{m:02d} -{won(a1)}円"))
        if spec["kind"] == "unpaid":
            target = item("🌐", "MOAHUB（韓国）",
                          f'{v["time_hm"]} ・ <span class="pend">お支払い手続き未完了</span>',
                          '<span class="pend">未完了</span>', f"{won(amount)} KRW")
            v_last = None
        else:
            target = item("🌐", "MOAHUB（韓国）",
                          f'{ef("t-dt", v["time_hm"])} ・ カード末尾{last4} ・ 支払い完了',
                          f"-{won(jpy)}円", ef("t-amount", f"{won(amount)} KRW"))
            D.append(dict(kind="jpy_conversion", text=f"-{won(jpy)}円"))
        rows += [o1, target] if later else [target, o1]
        prev = local - timedelta(days=1)
        rows.append(dh(prev))
        ch = int(rng.choice([3000, 5000, 10000]))
        rows.append(item("＋", "チャージ（銀行口座）", f"{int(rng.integers(8, 23)):02d}:{int(rng.integers(0, 60)):02d}", f"+{won(ch)}円"))
        D.append(dict(kind="topup", text=f"+{won(ch)}円"))
        h3, m3 = other_time(rng, local)
        a3 = int(rng.integers(30, 900)) * 10
        shop3 = JA_SHOPS[int(rng.integers(0, len(JA_SHOPS)))]
        rows.append(item("☕", shop3, f"{h3:02d}:{m3:02d} ・ カード末尾{last4 or '8810'}", f"-{won(a3)}円"))
        D.append(dict(kind="other_transaction", text=f"{shop3} {h3:02d}:{m3:02d} -{won(a3)}円"))
        rows.append(item("🎁", "ポイント還元", "キャンペーン", f"+{int(rng.integers(5, 90))} pt"))
        D.append(dict(kind="points", text="ポイント還元"))
        v["list"] = "\n".join(rows)
    return v, D


def render_html(spec, local, amount, last4, rng, edited_fields=()):
    v, D = fill(spec, local, amount, last4, rng, edited_fields)
    base = (HERE / "templates/base.css").read_text()
    tpl = (HERE / f"templates/{spec['style']}.html").read_text()
    html = Template(tpl).substitute(base=base, **v)
    # templates that hard-code the editable spans: add the edit classes
    for fid in edited_fields:
        html = html.replace(f'<span class="ef" id="{fid}">', f'<span class="ef edited {spec.get("estyle", "")}" id="{fid}">')
    return html, D


def main():
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    for split in ("heldout", "dev"):
        d = OUT / split
        if d.exists():
            shutil.rmtree(d)
        (d / "clean").mkdir(parents=True)

    jobs, plans = [], []
    for spec in SPECS:
        tr = truth(spec["case"])
        seed = int.from_bytes(spec["id"].encode(), "big") % (2**31)
        edit = spec.get("edit")
        shown_local, shown_amount = apply_edit(tr["local"], tr["amount"], edit)
        edited_fields = []
        if edit:
            if "amount" in edit:
                edited_fields.append("t-amount")
            if "time" in edit or "date" in edit:
                edited_fields.append("t-dt")
        # same rng seed for both renders so all distractors are identical
        h_orig, D = render_html(spec, tr["local"], tr["amount"], tr["last4"], np.random.default_rng(seed))
        (WORK / f"{spec['id']}_orig.html").write_text(h_orig)
        jobs.append(dict(html=str(WORK / f"{spec['id']}_orig.html"), png=str(WORK / f"{spec['id']}_orig.png"),
                         boxes=str(WORK / f"{spec['id']}_orig.boxes.json")))
        if edit:
            h_edit, _ = render_html(spec, shown_local, shown_amount, tr["last4"], np.random.default_rng(seed), edited_fields)
            (WORK / f"{spec['id']}_edit.html").write_text(h_edit)
            jobs.append(dict(html=str(WORK / f"{spec['id']}_edit.html"), png=str(WORK / f"{spec['id']}_edit.png"),
                             boxes=str(WORK / f"{spec['id']}_edit.boxes.json")))
        plans.append((spec, tr, shown_local, shown_amount, edited_fields, D, seed))

    (WORK / "jobs.json").write_text(json.dumps(jobs, ensure_ascii=False))
    subprocess.run([NODE, str(HERE / "render.mjs"), str(WORK / "jobs.json")], check=True)

    manifest = []
    for spec, tr, shown_local, shown_amount, edited_fields, D, seed in plans:
        sid = spec["id"]
        orig = Image.open(WORK / f"{sid}_orig.png").convert("RGB")
        ob = json.loads((WORK / f"{sid}_orig.boxes.json").read_text())
        if ob.get("__overflow"):
            print(f"WARNING {sid}: content overflows the screen")
        patches = []
        img = orig
        if edited_fields:
            edit_img = Image.open(WORK / f"{sid}_edit.png").convert("RGB")
            eb = json.loads((WORK / f"{sid}_edit.boxes.json").read_text())
            rng_e = np.random.default_rng(seed + 7)
            for fid in edited_fields:
                a, b = ob[fid], eb[fid]
                box = [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]
                img, pb = crude_paste(img, edit_img, box, rng_e, spec["recipe"])
                patches.append(dict(field=fid, box_px_clean=pb))
        clean_rel = f"{spec['split']}/clean/{sid}.png"
        img.save(OUT / clean_rel, optimize=True)
        ph = photo(img, spec["dist"], spec["s"], np.random.default_rng(seed + 1))
        photo_rel = f"{spec['split']}/{sid}.png"
        ph.save(OUT / photo_rel, optimize=True)

        shows_seconds = spec["style"] == "A_bank_detail"
        fmt = "%Y-%m-%d %H:%M:%S" if shows_seconds else "%Y-%m-%d %H:%M"
        shown_as = {
            "A_bank_detail": shown_local.strftime("%Y.%m.%d %H:%M:%S"),
            "B_card_push_list": shown_local.strftime("%m/%d %H:%M") + " (no year on screen)",
            "C_easypay_receipt": shown_local.strftime("%Y.%m.%d %H:%M"),
            "D_sms_approval": shown_local.strftime("%m/%d %H:%M") + " (no year on screen)",
            "E_jp_card_detail": shown_local.strftime("%Y/%m/%d %H:%M"),
            "F_jp_pay_history": f"{shown_local.month}月{shown_local.day}日 header + {shown_local.strftime('%H:%M')} (no year on screen)",
        }[spec["style"]]
        if spec["kind"] == "unpaid":
            status = "pending"
            verdict = "not_paid"
        elif spec["kind"] == "doctored":
            status = "approved"
            verdict = "no_matching_payment"
        else:
            status = "approved"
            verdict = "ledger_match"
        doctored = None
        if spec["kind"] == "doctored":
            frm, to = {}, {}
            e = spec["edit"]
            if "amount" in e:
                frm["amount"], to["amount"] = tr["amount"], shown_amount
            if "time" in e:
                frm["time"], to["time"] = tr["local"].strftime("%H:%M"), shown_local.strftime("%H:%M")
            if "date" in e:
                frm["date"], to["date"] = tr["local"].strftime("%Y-%m-%d"), shown_local.strftime("%Y-%m-%d")
            left = []
            if spec["style"] == "E_jp_card_detail" and "amount" in e:
                left.append("JPY conversion still matches the original KRW amount")
            if spec["style"] == "C_easypay_receipt" and "amount" in e:
                left.append("'주문금액' row still shows the original amount")
            if spec["style"] == "D_sms_approval":
                left.append("day separator and bubble timestamp still show the original date/time")
            if spec["style"] == "F_jp_pay_history" and "amount" not in e:
                left.append("JPY amount unchanged (consistent with original KRW)")
            doctored = dict(**{"from": frm, "to": to}, edit_look=spec["estyle"], paste_recipe=spec["recipe"],
                            patches=patches, tells_left_on_screen=left)
        manifest.append(dict(
            id=sid, split=spec["split"], file=photo_rel, clean_file=clean_rel, lang=spec["lang"],
            style=spec["style"], kind=spec["kind"], case=spec["case"], sender_email=CASES[spec["case"]]["email"],
            message=spec["msg"],
            gold=dict(amount=shown_amount, currency="KRW", paid_at_local=shown_local.strftime(fmt),
                      shown_as=shown_as, utc_offset="+09:00",
                      card_last4=tr["last4"] if spec["kind"] != "unpaid" else None,
                      status=status, merchant="MOAHUB"),
            ledger_payment_id=tr["pay"] if spec["kind"] == "true" else None,
            expected_verdict=verdict, doctored=doctored, distractors=D,
            dark_mode=spec["dark"], distortions=spec["dist"], distortion_strength=spec["s"],
            difficulty=spec["diff"], seed=seed,
        ))

    with open(OUT / "manifest.jsonl", "w") as f:
        for m in manifest:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")

    for split in ("heldout", "dev"):
        items = []
        for m in manifest:
            if m["split"] != split:
                continue
            lab = f"{m['id']} {m['kind']} {m['lang']} {m['difficulty']}"
            sub = m["style"]
            if m["doctored"]:
                sub2 = " ".join(f"{k}:{m['doctored']['from'][k]}→{m['doctored']['to'][k]}" for k in m["doctored"]["to"])
            else:
                sub2 = f"case {m['case']} {m['gold']['amount']:,} {m['gold']['paid_at_local'][5:16]}"
            items.append((OUT / m["file"], [lab, sub, sub2]))
        contact_sheet(items, OUT / f"contact_{split}.jpg", cols=4 if split == "heldout" else 3)
    print(f"wrote {len(manifest)} images")


if __name__ == "__main__":
    main()
