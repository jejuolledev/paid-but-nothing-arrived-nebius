# Paid, but nothing arrived

> Your customer already has proof they paid. This agent finds yours.

**Check it in three steps (no login, each step answers in under 5 seconds):**
1. Open **TRY_IT_URL**.
2. Click **See it in 30 seconds**. A customer's card alert says 9,900 won on the 20th; Nemotron 3.5 Super VL reads it and
   the payment ledger has **no payment at that time**. The customer answers *"Sorry, it was the 19th"* and sends the
   card-statement line; Nemotron 3.5 Super VL reads the statement, the agent checks the ledger again, it **matches**, the
   money chain shows the email never arrived, and the reply is rewritten. (Words alone never confirm a payment: they
   only change what the agent looks for, and it asks for the statement line.) (Recorded live runs on Token Factory; labelled with the time they were recorded.)
3. Click *Same message, turn by turn* to watch the model choose each lookup itself (payments, then the order behind the payment, then its history), or click any example, then **Run it live now** to make the same calls to Token Factory yourself (4 per hour per visitor).

**What it does:** a customer writes *"돈 냈어요, 이거 보세요"* ("I paid, here's proof") with a phone photo of their
banking or card app. **Nemotron 3.5 Super VL** reads the payment line (not the balance, the running total, the ad or the
phone's clock); the **payment provider's ledger** checks it: same amount, within ten minutes. The money chain shows the one
link where the money stopped (**card → payment provider → order → credits → mail**) with the rows that prove it, a reply
in the customer's language (Korean, Japanese, English), and a fix that runs only after the seller clicks Approve. When the
customer answers, the agent reads the answer and checks again (a second turn, not a new case). The model cannot spot an
edited screenshot; the ledger can, because it has no such payment. And sometimes the honest answer is *"Nothing is broken.
You were never charged."*

Models per job, all on Token Factory: **Nemotron 3.5 Super VL** reads the screenshot · **Nemotron 3.5 Lightning**
reads the message, plans the lookups and reads the customer's answer · **Nemotron 3 Ultra** re-reads when the first
reading is unsure · **Nemotron 3 Super** writes the cited explanation and the reply. The page shows each call's model,
time, tokens and cost.

**All data is synthetic** (an invented shop, `@example.com` customers, public test card numbers, rendered phone screens).
We have not measured real customer photos yet.

**Watch (under 3 min):** VIDEO_URL

Track: **Best Apps and Agents** · Team: MoaHub (solo, Korea) · License: MIT

---

## Why this exists
I run a small online shop. The message I dread most is "I paid but nothing arrived." Answer slowly and it becomes a card dispute. The answer is spread over four places: the payment provider, our orders database, the server logs and the mail provider. Five of the six example message cases are bugs I found in my own checkout (two happened on real payments), rebuilt with synthetic data; the sixth is a variation added to test the agent.

## Which Nemotron does what (all on Nebius Token Factory)

| Job | Model (env var) | What it does | How code checks it |
|---|---|---|---|
| 0. Read the screenshot | `nvidia/Nemotron-3.5-Super-VL` (`LLM_VISION_MODEL`) | Finds the one payment to the shop on a phone photo of a banking / card / pay app (Korean, Japanese, English), not the balance, points, instalment count, the phone's clock, ads, other rows or the yen conversion. Returns amount, date, time, card last-4, status and the exact text it read, as strict JSON. | The photo's metadata is removed and it is resized; on a Mac, e-mail addresses and long account/card numbers found by on-device OCR are blurred before sending. The amount must equal its own on-screen quote; malformed values are dropped and shown. **The payment provider's ledger decides**: same amount, within ±10 minutes, and the same last-4 when both show one. A photo the ledger has never seen stays "not in the ledger", whatever it shows. |
| 1. Read + plan | `nvidia/Nemotron-3_5-Lightning` (`LLM_MODEL_INTAKE`) | Finds the sender among the addresses in the message (a spouse's address, a CC, a forwarded header and the shop's own address are not the sender); pulls out the claims (amount, when, which pack, what went wrong, someone else's order number they ask for); writes a plan of up to five read-only lookups. | Addresses become `EMAIL_1`, `EMAIL_2` (first letter + domain) and card digits are removed before the model sees the message. Every value must be stated in the message (digits, 만/천 units or Korean number words); anything else is **dropped and shown**. The plan runs only on the sender's own trail. |
| 1b. Re-read when unsure | `nvidia/Nemotron-3-Ultra-550b-a55b` (`LLM_MODEL_ESCALATE`) | Called only when code finds the first reading unsure (no JSON, no sender although there are addresses, unsupported values, or the reader says so). | Same checks; its answer is used only if it is itself clean (or if the first reader returned nothing usable). The page says why it was called. |
| 1c. Read the customer's answer | `nvidia/Nemotron-3_5-Lightning` (`LLM_MODEL_FOLLOWUP`) | Second turn: the date, time or amount the customer now gives ("it was the 19th"), as strict JSON. | A value is kept only if the answer itself writes it (a month the customer did not write is not taken). The answer can only change what is looked for; the ledger decides again. A new screenshot runs the screenshot step again. |
| 2. Explain + reply | `nvidia/nemotron-3-super-120b-a12b` (`LLM_MODEL_EXPLAIN`, `LLM_MODEL_REPLY`) | The explanation, citing rows, and the reply in the customer's language (Korean, Japanese, English). | Every sentence is checked against the rows it cites. A reply that promises money, moves credits before the customer confirms, or suggests a screenshot is fake → the standard reply is used. |

Each call's model, time, tokens and estimated cost (catalog prices) are on the page, with a total per case.

The **verdict and the fix never come from the model.** `agent/chain.py` walks the money chain (card authorized → payment provider paid → order confirmed → credits granted → mail delivered) and marks each link green, red or grey with the rows that decided it.

The page also shows **what the customer says vs. the records** (e.g. "you say 29,900; the ledger shows 24,900 PAID") and **what the rules alone would have found** without the model reading the message.

## Measured
Every run is logged in `docs/measurements/` and summarised in `docs/measurements.md` (screenshots) and `docs/measurements_nebius.md` (messages). The held-out sets were built by a separate agent that never saw the prompts or the code, and committed before the first model run (git history). We tuned only on the dev sets.

**Screenshots** (`docs/eval/screens/`, 16 held-out synthetic phone photos in Korean and Japanese, 6 invented app styles; 7 genuine payments that are in the ledger, 1 unfinished checkout, 8 with the amount, time or date edited):

| Reader of the photo | Amount right | Date + time right | Verdict right **with** the fields right |
|---|---|---|---|
| Free on-device OCR (macOS Vision) + today's rules | 1/16 | 0/16 | 0/16 |
| Free on-device OCR + payment-word rules | 5/16 | 8/16 | 3/16 |
| **Nemotron 3.5 Super VL on Token Factory** | **14/16** | **14/16** | **14/16** |
| Same Nemotron given only the OCR text (no image) | 15/16 | 13/16 | 13/16 |

Held-out, run once (2026-10-29, commit 9124eb9), reasoning off, strict JSON schema; average 5.5 s and about $0.0008 per photo.
The two misses: a card push list where it took the account's running total (3,158,900) as the payment, so the ledger found nothing (a wrong "not in the ledger", never a wrong "paid"); and an unfinished easy-pay checkout it did not recognise as a payment screen ("could not read" instead of "not paid").
**What this shows, honestly:** given only the OCR lines, the same Nemotron gets 13/16. Most of the gain over the rules comes from Nemotron choosing the right line on a crowded screen, not from reading pixels better than OCR. The image still matters where there is no on-device OCR (the hosted demo) and on two Japanese pay-history photos where the date sits in a section header above the time: reading the image got the date, reading the OCR lines did not. Edited screenshots: 8/8 ended as "not in the ledger" with Nemotron reading the image (6/8 when it got only the OCR text: one call ran out of tokens, one date was missed). The rules also reached 8/8, but by misreading the numbers. The ledger is what rejects an edit; the reader cannot spot it. On the clean (unphotographed) screens Nemotron gets 15/16.
After the held-out run, one prompt line was added from a dev example (running totals such as 누적 are not the payment); the held-out set was not run again (`docs/measurements.md`, note).

**Messages** (Korean-heavy held-out set `docs/eval/text_fallback.jsonl`, 22: 만/천 amounts, Korean number words, forwarded headers, a spouse writing, requests for someone else's order):

| Reader | Sender found | Right order + broken link |
|---|---|---|
| Rules only | 16/22 | 21/22 |
| **Nemotron 3.5 Lightning, Ultra when unsure** (fixed plan of lookups) | **20/22** | 20/22 |
| **Same, the model picks each lookup turn by turn** (measured once, after the run above) | **21/22** | **21/22** |

Held-out, run once (2026-10-29, commit c4748e2). Nemotron finds who is writing far more often; end to end the rules get one more right. Its two end-to-end misses: a spouse asking about the wife's order (it read the writer's own unrelated order), and a prompt-injection message asking for another customer's card digits, where it named no sender, so **nobody's records were read** (counted wrong, safe on purpose). Ultra was called on 16 of 22 (Lightning often says it is unsure on Korean threads); average 15.5 s of model time and $0.005 per message.
Fair note: while tuning on the dev set we also taught the shared lookup code that the shop's own address and no-reply senders are never the customer; that lifted the rules row from 17/22 to 21/22 too, and both rows above use it.

English-heavy set (40): rules only 38/40, **Nemotron 40/40** (one model call failed on h16; the run still reached the right order; complaint read right 29/40).

From the version this builds on (still true of the verifier): six seeded cases right 6/6; the sentence checker caught 32 of 40 wrong sentences written by a separate model and wrongly rejected 2 of 20 true ones (`scripts/claim_eval.py`). 65 automated tests (`pytest`, never call a paid model).

## Run it yourself
```bash
git clone https://github.com/jejuolledev/paid-but-nothing-arrived-nebius && cd paid-but-nothing-arrived-nebius
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python data/gen_synthetic.py && .venv/bin/python -m pytest -q        # 65 tests, no key needed
cp .env.example .env.local    # put your Token Factory key in NEBIUS_API_KEY
.venv/bin/uvicorn app.main:app --port 8765                                     # open http://127.0.0.1:8765
```
No key? It still runs: the rules-only lookup and the verifier answer, and the page says no model was used. `LLM_FAKE=1` runs a scripted stand-in for trying the page; it is labelled **FAKE** everywhere and refused in public mode.

Check which NVIDIA models your key can call: `.venv/bin/python scripts/tf_models.py`. Pick models per step with `LLM_MODEL_INTAKE` / `LLM_MODEL_EXPLAIN`.

Public demo mode (what the hosted link runs): `DEMO_PUBLIC=1` — per-visitor data, recorded example runs (`scripts/precompute.py`), live runs limited per visitor and per day, the key only on the server, no API docs exposed. Deploy: `Dockerfile` + `deploy/cloudrun.sh`.

## How it is built
- `agent/llm.py` — Token Factory client (OpenAI-compatible), per-call log of model, time and tokens.
- `agent/intake.py` — placeholders, the reading/planning prompt, `ground()`, plan execution.
- `agent/agent_loop.py` — `Scope`: the sender's own trail; an optional turn-by-turn loop (off in the public demo).
- `agent/chain.py` — the verifier. `agent/investigator.py` — the pipeline and the sentence checker. `agent/compare.py` — claims vs records.
- `agent/actions.py` — human-approved fixes with an audit log. `app/` — FastAPI + one page.

## What existed before this hackathon, and what is new
The submission period runs from 2026-08-26. This project was **first written on 2026-10-22–25** for another event (the Open Agent Hackathon), where it ran on a local data platform and on NVIDIA's own hosted Nemotron endpoint. That version is public and frozen at tag `submitted-2026-10-25` of github.com/jejuolledev/paid-but-nothing-arrived; its docs are kept in `docs/open-agent-2026-10-25/`. The first commit of this repository is that snapshot, unchanged except that the old demo video files, Cursor session notes and a comic draft were removed and its docs were moved to `docs/open-agent-2026-10-25/`.

**Added for Nebius × NVIDIA (2026-10-27 onward, see git log):**
- Nemotron on **Nebius Token Factory** is now the model for every step (`agent/llm.py`).
- **Screenshot proof** (`agent/proof.py`): Nemotron 3.5 Super VL reads the customer's payment screenshot, code checks the fields, the ledger decides; edited screenshots land in "not in the ledger".
- New model step: **reading the message and planning the lookups** (`agent/intake.py`), with grounding and a sender-scoped plan. Before, the first address and the first order number in the message were taken by a regex.
- **Customer's claims vs. records** (`agent/compare.py`) and the **rules-only comparison** on every result.
- Held-out sets frozen before any model run: **40 messages** (English-heavy), **22 Korean-heavy messages (Korean and Japanese)** (`docs/eval/text_fallback.jsonl`) and **16 phone photos** (`docs/eval/screens/`), with `scripts/intake_eval.py` and `scripts/proof_eval.py` (rules or free OCR vs. model).
- **Public demo mode**: per-visitor data, recorded runs, rate limits, key server-side; Dockerfile and Cloud Run script.
- Page: what the model read, what it dropped, the plan, model calls with time and tokens.

## Limitations (published on purpose)
- The second turn reads dates, times and amounts only; anything else the customer says is shown to the seller but not used to look anything up. Not measured on a held-out set (the dev example and tests only).
- The verifier knows five kinds of break; a new kind lands in "not verified" instead of being guessed.
- Relative dates ("yesterday") are not checked against the ledger, because the message date is unknown.
- The intake can still pick the wrong sender when the message itself is ambiguous; the seller sees the sender and the dropped values on the page before sending anything.
- Measured failures (held-out): the running-total misread and the unfinished checkout above (photos); the spouse case and the injection case (messages). Lightning asks Ultra for help on most Korean threads, which roughly triples the cost of those messages.
- The photos are synthetic (rendered app screens with photo-like distortion); we have not measured real customer photos.
- Nemotron cannot tell an edited screenshot from a real one. Only the ledger can, and only for payments to this shop.
- The sender comes from the message body (the page has no From field). With several customer addresses and no reader to tell them apart (no key, past the live-run limit, a failed call), nobody's records are read. With a single address, the agent trusts it: someone who writes only another customer's address is treated as that customer, so the seller should check the address matches the e-mail's real sender before sending the reply. A message can also try to steer the reader ("the sender is …"); the page always shows which address was used.
- All data is synthetic (`@example.com`, public test card numbers). On real data, the seller decides whether masked rows may go to Token Factory.

## Feedback on Nebius Token Factory and NVIDIA Nemotron
See [docs/feedback.md](docs/feedback.md) (also pasted in the submission form).

## License
MIT — see [LICENSE](LICENSE).
