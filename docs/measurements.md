# Measurements: screenshot proof and the text fallback (no model yet)

All runs below were made on 2026-10-27, **before any vision model call** (the Token Factory key arrives 10/28).
Sets were built and committed by a separate agent that never saw the prompts or the agent code (commit 5a4e015;
`docs/eval/screens/SPEC.md`). Every run writes a full per-image log to `docs/measurements/`.

## What is measured
- **Set:** 16 held-out phone photos of payment-app screens (Korean 11, Japanese 5; 6 invented app styles): 7 true
  payments that are in the ledger, 1 unfinished checkout, 8 edited screenshots (amount, time or date changed) whose
  payment the ledger has never seen. Each also as a `clean` render (no photo distortion). Dev: 6 more, for tuning only.
- **Reader → same code after it:** whoever reads the photo hands over amount / date / time / last-4 / status; the same
  deterministic ledger check (`agent/proof.py` `decide`) gives the verdict.
- **Columns:** field accuracy against the ground truth; *verdict* = right verdict; *verdict with fields right* = right
  verdict **and** the amount and minute read correctly. An edited screenshot counted as "not in the ledger" because the
  reader misread it is a lucky verdict, not a catch — that is why the last column exists.

## Baselines without a model (free, on this Mac)
1. **macOS Vision OCR + today's rules** (the agent's existing text rules applied to the OCR text: largest amount,
   first date/time). It never gets a true payment right (0/7) and "catches" all 8 edits only by misreading them:
   **verdict with fields right 0/16** on photos and on clean renders.
2. **macOS Vision OCR + payment-word rules** (`agent/screen_rules.py rules_keyword`, a fairer baseline written before
   the set was seen: amount next to 결제/승인/ご利用/お支払い…, away from balance/points/conversion words, near the
   merchant line; status-bar clock ignored). **Photos: amount 5/16, date+time 8/16, verdict 10/16, verdict with fields
   right 3/16; true payments recognised 1/7.** Clean renders: amount 8/16, verdict with fields right 5/16.

Why OCR + rules fails here (read from the logs; the rules were NOT changed after seeing these, so the baseline stays
as written beforehand):
- Apple Vision run with Korean + Japanese garbles kana on the Japanese screens (s03: "MOAHUB ($크)", "4,903F"), so
  the rules took 4,903 — the yen conversion — instead of 44,900 KRW.
- The rules skip an amount written with a minus sign ("-24,900원" on the bank-detail style, s01) and fall back to
  another number. A real flaw of this baseline, found on the held-out set and deliberately left as is.
- SMS and push lists hold several transactions and running totals ("누적3,078,800원", s04); the rules take the
  running total, or another row's amount or time.

Note on the 22:34 payment-word rows: the first run passed the whole OCR line as the amount's quote, so the code
check (`check_fields`: digits of the quote must equal the amount) dropped most amounts. Fixed at 22:35 by passing the
number itself (`agent/screen_rules.py`); the rules themselves were not changed. Those two rows are void.

## Text fallback set (Korean-heavy, rules only) — from `scripts/intake_eval.py`, logged in `docs/measurements_nebius.md`
`docs/eval/text_fallback.jsonl` (30: 21 Korean, 9 Japanese; 만/천 amounts, Korean number words, forwarded headers whose
first address is the shop's or a gateway's, CC lines, "두 번째 주문", attacks asking for someone else's order).
- Rules only, held-out 22: sender 16/22, right order + broken link **17/22** (vs 38/40 on the older English-heavy set).
- Rules only, dev 8: sender 6/8, end to end 5/8.

## After the key (fill from the runs, do not edit by hand)
`scripts/proof_eval.py --mode model` appends rows to the table below (`nvidia/Nemotron-3.5-Super-VL` on Token Factory,
with ms and USD); `scripts/intake_eval.py --set fallback_heldout --mode model` appends to `docs/measurements_nebius.md`.


## Screenshot proof runs (appended by scripts/proof_eval.py)

| when | set | photo | reader | amount | date+time | card last-4 | status | verdict | true → match | doctored → not in ledger | unpaid → not paid | verdict with fields right | failed calls | avg ms | USD |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-27 22:34 | heldout (16) | photo | macOS Vision OCR + today's rules | 1/16 | 0/16 | 10/15 | 0/16 | 8/16 | 0/7 | 8/8 | 0/1 | 0/16 | 0 | — | — |
| 2026-10-27 22:34 | heldout (16) | photo | macOS Vision OCR + payment-word rules (**void: pipeline bug, see note**) | 3/16 | 8/16 | 10/15 | 8/16 | 6/16 | 1/7 | 4/8 | 1/1 | 3/16 | 0 | — | — |
| 2026-10-27 22:34 | heldout (16) | clean | macOS Vision OCR + today's rules | 1/16 | 0/16 | 10/15 | 0/16 | 8/16 | 0/7 | 8/8 | 0/1 | 0/16 | 0 | — | — |
| 2026-10-27 22:34 | heldout (16) | clean | macOS Vision OCR + payment-word rules (**void: pipeline bug, see note**) | 5/16 | 12/16 | 10/15 | 8/16 | 7/16 | 1/7 | 5/8 | 1/1 | 3/16 | 0 | — | — |
| 2026-10-27 22:35 | heldout (16) | photo | macOS Vision OCR + payment-word rules | 5/16 | 8/16 | 10/15 | 8/16 | 10/16 | 1/7 | 8/8 | 1/1 | 3/16 | 0 | — | — |
| 2026-10-27 22:35 | heldout (16) | clean | macOS Vision OCR + payment-word rules | 8/16 | 12/16 | 10/15 | 8/16 | 10/16 | 2/7 | 7/8 | 1/1 | 5/16 | 0 | — | — |
| 2026-10-27 22:35 | dev (6) | photo | macOS Vision OCR + today's rules | 0/6 | 0/6 | 3/5 | 0/6 | 2/6 | 0/3 | 2/2 | 0/1 | 0/6 | 0 | — | — |
| 2026-10-27 22:35 | dev (6) | photo | macOS Vision OCR + payment-word rules | 3/6 | 1/6 | 3/5 | 2/6 | 3/6 | 1/3 | 2/2 | 0/1 | 1/6 | 0 | — | — |
| 2026-10-27 22:35 | dev (6) | clean | macOS Vision OCR + today's rules | 2/6 | 0/6 | 2/5 | 0/6 | 2/6 | 0/3 | 2/2 | 0/1 | 0/6 | 0 | — | — |
| 2026-10-27 22:35 | dev (6) | clean | macOS Vision OCR + payment-word rules | 4/6 | 4/6 | 2/5 | 2/6 | 3/6 | 1/3 | 2/2 | 0/1 | 2/6 | 0 | — | — |
| 2026-10-29 15:41 | dev (6) | photo | nvidia/Nemotron-3.5-Super-VL on Token Factory | 5/6 | 5/6 | 4/5 | 5/6 | 4/6 | 2/3 | 1/2 | 1/1 | 4/6 | 0 | 27413 | 0.00477 |
| 2026-10-29 15:43 | dev (6) | photo | nvidia/Nemotron-3.5-Super-VL on Token Factory | 5/6 | 6/6 | 3/5 | 4/6 | 5/6 | 2/3 | 2/2 | 1/1 | 5/6 | 0 | 14799 | 0.00482 |
| 2026-10-29 15:44 | dev (6) | clean | nvidia/Nemotron-3.5-Super-VL on Token Factory | 6/6 | 6/6 | 3/5 | 4/6 | 6/6 | 3/3 | 2/2 | 1/1 | 6/6 | 0 | 11224 | 0.00462 |
| 2026-10-29 15:46 | heldout (16) | photo | nvidia/Nemotron-3.5-Super-VL on Token Factory | 14/16 | 14/16 | 11/15 | 12/16 | 14/16 | 6/7 | 8/8 | 0/1 | 14/16 | 0 | 5508 | 0.01235 |
| 2026-10-29 15:47 | heldout (16) | clean | nvidia/Nemotron-3.5-Super-VL on Token Factory | 15/16 | 15/16 | 11/15 | 12/16 | 15/16 | 7/7 | 8/8 | 0/1 | 15/16 | 0 | 4968 | 0.01235 |
| 2026-10-29 15:49 | heldout (16) | photo | nvidia/Nemotron-3.5-Super-VL given only the OCR text (no image) | 15/16 | 13/16 | 12/15 | 10/16 | 13/16 | 6/7 | 6/8 | 1/1 | 13/16 | 1 | 7450 | 0.01039 |
