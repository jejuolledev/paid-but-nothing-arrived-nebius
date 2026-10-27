# Screenshot eval set (frozen)

Built by a separate agent that did **not** read the agent code, prompts, app, tests or
`gen_synthetic.py`. Inputs used: `data/out/payments.csv`, `orders.csv`, `grants.csv`,
`cases.json`, and the first 3 lines of `docs/eval/intake_heldout.jsonl` (format only).

Rebuild (byte-identical, fixed seeds):

```
.venv/bin/python scripts/eval_screens/build.py          # images, manifest, contact sheets
.venv/bin/python scripts/eval_screens/text_fallback.py  # docs/eval/text_fallback.jsonl
.venv/bin/python scripts/eval_screens/verify_manifest.py
```

## Contents

| split | true | unpaid | doctored | total |
|---|---|---|---|---|
| heldout | 7 | 1 | 8 | 16 |
| dev | 3 | 1 | 2 | 6 |

Each image has a photo variant (`<split>/<id>.png`) and the undistorted render
(`<split>/clean/<id>.png`, the "easy" variant; for doctored images the clean file already
contains the edit). `manifest.jsonl` has one line per image; `contact_heldout.jpg` /
`contact_dev.jpg` are thumbnail sheets of the photo variants.

`gold` is what the screen **shows** as the MOAHUB payment (for doctored images: the edited
values). `paid_at_local` is KST/JST (UTC+9, identical) at the precision shown; style A shows
seconds, the others minutes. `gold.shown_as` records the literal on-screen form; styles B, D
and F show no year (the year is 2026 from context).
`expected_verdict`: `ledger_match` (true), `no_matching_payment` (doctored), `not_paid` (unpaid).

## App styles (all fictional, no real brand names, logos or colour schemes)

| id | lang | what it imitates | key fields |
|---|---|---|---|
| A_bank_detail | ko | bank app, one transaction detail ("누리뱅크") | amount, date+time **with seconds**, card ****last4, balance after |
| B_card_push_list | ko | card-company notification list ("솔카드") | several approval pushes; target push has `MM/DD HH:MM`, no year |
| C_easypay_receipt | ko | easy-pay receipt ("도토리페이"); unpaid variant = checkout left before choosing a card | big amount, 결제일시, card ****last4 |
| D_sms_approval | ko | SMS card-approval texts ("가람카드") | `MM/DD HH:MM`, plus a day separator and bubble timestamp |
| E_jp_card_detail | ja | Japanese card app usage detail ("ミナトカード") | KRW local amount + JPY conversion (rate 0.1092), 末尾last4 |
| F_jp_pay_history | ja | Japanese pay-app history list ("ひかりペイ") | primary amount in **JPY**, KRW in a sub-line, date only in the group header |

Ledger truth used (UTC → +9): pay_0901 24,900 / 10-13 21:00:40 / 4242; pay_0902 9,900 /
10-16 05:00:30 / 4444; pay_0903 44,900 / 10-17 10:00:00 / 0005; pay_0904 9,900 /
10-19 03:00:00 / 1117; pay_0906 24,900 / 10-21 02:00:20 / 5556 (payer
liam.patel906@example.com; the order is under the typo address). Case 5 (ord_0905, 24,900,
order 10-20 14:00) has no payment: s06 shows a "결제 대기 · 미승인" checkout, d04 an
"お支払い手続き未完了" history row.

## Distractors (recorded per image in `distractors`)

Chosen because they are what real customer screenshots almost always contain:

- **status_bar_clock** – a time that differs from the payment time by at least 2 h (people screenshot later).
- **balance / available_credit / cumulative_spend / statement_due** – larger KRW/JPY figures next to the payment.
- **points / cashback / ad_banner / ad_sms** – promo numbers ("최대 20,000원", "500 pt").
- **installment** – another approval with 할부 3개월 and its own amount/time.
- **other_transaction** – other merchants, amounts and times in the same list, sometimes the same day.
- **jpy_conversion / fx_rate** – on Japanese screens the most prominent number is yen, not the KRW charge.
- **saved_card** (unpaid screen) – card last-4 digits that were *never used*, plus a "24,900원 결제하기" button.
- **order_amount_row / approval_number** – receipt rows that repeat or resemble amounts.

## Doctoring recipe

1. Render the true screen (`_orig`) and a second render with the edited value(s) where the
   edited span gets an "edit look" class (`e1` lighter weight + bigger, `e2` Helvetica digits
   + tracking, `e3` smaller + 1 px baseline shift, `e4` heavier + tight tracking).
2. Find the pixels that differ inside the field box, pad 3–6 px, cut that patch from the edit
   render, and paste it on the original with: a background tone shift (−5…+6), optional
   JPEG re-save of the patch (q 40–65), optional hard-threshold "no antialias" text (s11),
   optional 1 px offset, optional JPEG re-save of the surrounding region (q 45–50).
3. Untouched dependent fields are left as they were, like a real crude edit:
   JPY conversion (E), "주문금액" row and product name (C), the SMS day separator and bubble
   timestamp (D), the KRW sub-line (F). These are recorded in `doctored.tells_left_on_screen`.

Exact before/after values and patch boxes are in `doctored`. Every doctored claim has no
ledger row for that sender with that amount within ±10 min (checked by `verify_manifest.py`;
also no row for any customer with the same amount+last4 in that window).

| id | style | case | change |
|---|---|---|---|
| s09 | A | 2 | amount 9,900 → 44,900 |
| s10 | B (dark) | 1 | time 21:00 → 20:00 |
| s11 | D | 3 | date 10-17 → 10-16 |
| s12 | E | 6 | amount 24,900 → 44,900 (yen unchanged) |
| s13 | F (dark) | 2 | time 05:00 → 04:12 |
| s14 | C | 4 | amount 9,900 → 24,900 |
| s15 | A | 4 | time 03:00:00 → 02:30:00 |
| s16 | B | 6 | amount 24,900 → 44,900 and time 02:00 → 01:40 |
| d05 | B | 4 | date 10-19 → 10-20 |
| d06 | E | 1 | time 21:00 → 22:00 |

## Photo distortion recipe (`distort.photo`, strength s in 0..1)

Applied in this order when listed: moiré (two crossed sine gratings, amplitude 10+22s, slight
RGB tint) → edge crop (top/right/bottom, 4–10 %) → dark bezel + textured surface →
perspective (corner jitter 2–9 %) → rotation (1.5–8°) → dim → glare hotspot (elliptical,
+70…160) → Gaussian blur (0.8–2.4 px) or hand-shake motion blur → Gaussian noise (σ 4–14) →
downscale (0.78−0.25s) → JPEG (q 70−45s). Dark mode is a render-time theme, not a filter.
Difficulty labels: easy = mild warp/rotate only; medium = 3–4 effects at s≈0.4–0.6;
hard = 4–5 effects at s≥0.7 (s04, s07, s11, s13, s15). Hard images were checked by eye and
remain human-readable.

## How this differs from real customer photos (honest notes)

- Screens are clean HTML renders: perfect alignment, one font family per screen, no real app
  chrome quirks (truncated merchant names like "모아허브(MOA…", ellipses, Korean bank-specific
  abbreviations, tiny legal text).
- Real photos have true optical moiré, rolling-shutter bands, finger occlusion, reflections of
  the photographer, mixed lighting colour casts and phone-camera sharpening/HDR halos; ours are
  approximations. Real screenshots (not photos) are also common and are covered only by the
  clean variants.
- Doctoring is mechanical (diff-patch). Real forgeries range from far cruder (visibly
  mismatched fonts, misaligned digits) to far better (re-rendered whole screen). The set has
  no fully re-rendered fakes, so a detector that keys on patch artefacts will look better here
  than in practice; the gold check that matters is the ledger lookup.
- Only six customers and three amounts; real traffic has partial refunds, split payments,
  foreign-currency fees on KRW cards, and screenshots of the wrong merchant.
- Masked names, approval numbers and other customers' figures are random but plausible.
- All styles use system fonts (Apple SD Gothic Neo, Hiragino Sans) rendered by headless
  Chromium at 390×844 CSS px, device scale 2.

## Text fallback set

`docs/eval/text_fallback.jsonl` – 30 items (21 ko, 9 ja; several mixed with English), first 8
`dev`, rest `heldout`. Shape follows `intake_heldout.jsonl` plus `gold.lang`, `gold.mixed_en`,
`gold.attack` (4 social-engineering items; `target_order` is the attacker's own order),
`gold.third_party` (spouse writing about the partner's order). Built so regex rules fail:
amounts as 만/천 ("2만4900원", "4만 4천9백원") and number words ("이만 사천구백 원",
"사만사천구백원"), forwarded headers whose first address is the shop's or a third party's
(PSP, bounce daemon), Cc/참조 lines naming other customers, "두 번째 주문"/"二つ目の注文"
meaning the second payment attempt or a duplicate grant, a full card number typed by mistake,
and times/last-4 digits next to amounts. `generated by scripts/eval_screens/text_fallback.py`,
which validates every email, order id and amount against the CSVs.
