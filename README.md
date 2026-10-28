# Paid, but nothing arrived

> Your customer already has proof they paid. This agent finds yours.

**In ten seconds:** a customer writes *"돈 냈어요, 이거 보세요"* ("I paid, here's proof") and drops a phone photo of their
banking app. **Nemotron 3.5 Super VL on Nebius Token Factory** reads the photo — the payment line, not the balance,
the points or the phone's clock — and the seller's own payment ledger checks it: same amount, same minute. Then the
money chain shows the one link where the money got stuck (**card → payment provider → order → credits → mail**), with
the rows that prove it, a reply in the customer's language (Korean, Japanese, English), and a fix that runs only
after the seller clicks Approve. Change one number on the screenshot and the ledger has never seen that payment. And
sometimes the honest answer is: *"Nothing is broken. You were never charged."*

Models per job, all on Token Factory: **Nemotron 3.5 Super VL** reads the screenshot · **Nemotron 3.5 Lightning**
reads the message and plans the lookups · **Nemotron 3 Ultra** re-reads only when that first reading is unsure ·
**Nemotron 3 Super** writes the cited explanation and the reply. The page shows each call's model, time, tokens and cost.

**Try it:** TRY_IT_URL — no login, no key. The six example buttons answer at once from a recorded live run; **Run it live now** calls Token Factory for real. Your Approve and Reset change only your own copy of the synthetic data.

**Watch (under 3 min):** VIDEO_URL

Track: **Best Apps and Agents** · Team: MoaHub (solo, Korea) · License: MIT

---

## Why this exists
I run a small online shop. The message I dread most is "I paid but nothing arrived." Answer slowly and it becomes a card dispute. The answer is spread over four places: the payment provider, our orders database, the server logs and the mail provider. The six example cases in this demo are bugs I found in my own checkout (two happened on real payments), rebuilt with synthetic data.

## Which Nemotron does what (all on Nebius Token Factory)

| Job | Model (env var) | What it does | How code checks it |
|---|---|---|---|
| 0. Read the screenshot | `nvidia/Nemotron-3.5-Super-VL` (`LLM_VISION_MODEL`) | Finds the one payment to the shop on a phone photo of a banking / card / pay app (Korean, Japanese, English), not the balance, points, instalment count, the phone's clock, ads, other rows or the yen conversion. Returns amount, date, time, card last-4, status and the exact text it read, as strict JSON. | The photo's metadata is removed and it is resized; on a Mac, e-mail addresses and long account/card numbers found by on-device OCR are blurred before sending. The amount must equal its own on-screen quote; malformed values are dropped and shown. **The payment provider's ledger decides**: same amount, same minute (±10), same last-4. A photo the ledger has never seen stays "not in the ledger", whatever it shows. |
| 1. Read + plan | `nvidia/Nemotron-3_5-Lightning` (`LLM_MODEL_INTAKE`) | Finds the sender among the addresses in the message (a spouse's address, a CC, a forwarded header and the shop's own address are not the sender); pulls out the claims (amount, when, which pack, what went wrong, someone else's order number they ask for); writes a plan of up to five read-only lookups. | Addresses become `EMAIL_1`, `EMAIL_2` (first letter + domain) and card digits are removed before the model sees the message. Every value must be stated in the message (digits, 만/천 units or Korean number words); anything else is **dropped and shown**. The plan runs only on the sender's own trail. |
| 1b. Re-read when unsure | `nvidia/Nemotron-3-Ultra-550b-a55b` (`LLM_MODEL_ESCALATE`) | Called only when code finds the first reading unsure (no JSON, no sender although there are addresses, unsupported values, or the reader says so). | Same checks; its answer is used only if it is itself clean. The page says why it was called. |
| 2. Explain + reply | `nvidia/nemotron-3-super-120b-a12b` (`LLM_MODEL_EXPLAIN`, `LLM_MODEL_REPLY`) | The explanation, citing rows, and the reply in the customer's language (Korean, Japanese, English). | Every sentence is checked against the rows it cites. A reply that promises money, moves credits before the customer confirms, or suggests a screenshot is fake → the standard reply is used. |

Each call's model, time, tokens and estimated cost (catalog prices) are on the page, with a total per case.

The **verdict and the fix never come from the model.** `agent/chain.py` walks the money chain (card authorized → payment provider paid → order confirmed → credits granted → mail delivered) and marks each link green, red or grey with the rows that decided it.

The page also shows **what the customer says vs. the records** (e.g. "you say 29,900; the ledger shows 24,900 PAID") and **what the rules alone would have found** without the model reading the message.

## Measured
Every run is logged in `docs/measurements/` and summarised in `docs/measurements.md` (screenshots) and `docs/measurements_nebius.md` (messages). The held-out sets were built by a separate agent that never saw the prompts or the code, and committed before the first model run (git history). We tuned only on the dev sets.

**Screenshots** (`docs/eval/screens/`, 16 held-out synthetic phone photos in Korean and Japanese, 6 invented app styles; 7 real payments, 1 unfinished checkout, 8 with the amount, time or date edited):

| Reader of the photo | Amount right | Date + time right | Verdict right **with** the fields right |
|---|---|---|---|
| Free on-device OCR (macOS Vision) + today's rules | 1/16 | 0/16 | 0/16 |
| Free on-device OCR + payment-word rules | 5/16 | 8/16 | 3/16 |
| Nemotron 3.5 Super VL on Token Factory | FILL | FILL | FILL |
| Same Nemotron given only the OCR text (no image) | FILL | FILL | FILL |

**Messages** (Korean-heavy held-out set `docs/eval/text_fallback.jsonl`, 22: 만/천 amounts, Korean number words, forwarded headers, a spouse writing, requests for someone else's order):

| Reader | Sender found | Right order + broken link |
|---|---|---|
| Rules only | 16/22 | 17/22 |
| Nemotron (Lightning, Ultra when unsure) | FILL | FILL |

Older English-heavy set (40): rules only 38/40, Nemotron FILL. FILL: what the model still misses (ids from the log).

From the version this builds on (still true of the verifier): six seeded cases right 6/6; the sentence checker caught 32 of 40 wrong sentences written by a separate model and wrongly rejected 2 of 20 true ones (`scripts/claim_eval.py`). 51 automated tests (`pytest`, never call a paid model).

## Run it yourself
```bash
git clone REPO_URL && cd paid-but-nothing-arrived-nebius
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python data/gen_synthetic.py && .venv/bin/python -m pytest -q        # 51 tests, no key needed
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
The submission period runs from 2026-08-26. This project was **first written on 2026-10-22–25** for another event (the Open Agent Hackathon), where it ran on a local data platform and on NVIDIA's own hosted Nemotron endpoint. That version is public and frozen at tag `submitted-2026-10-25` of github.com/jejuolledev/paid-but-nothing-arrived; its docs are kept in `docs/open-agent-2026-10-25/`. The first commit of this repository is that snapshot, unchanged except that the old demo video files were removed.

**Added for Nebius × NVIDIA (2026-10-27 onward, see git log):**
- Nemotron on **Nebius Token Factory** is now the model for every step (`agent/llm.py`).
- New model step: **reading the message and planning the lookups** (`agent/intake.py`), with grounding and a sender-scoped plan. Before, the first address and the first order number in the message were taken by a regex.
- **Customer's claims vs. records** (`agent/compare.py`) and the **rules-only comparison** on every result.
- A **40-message held-out set** and `scripts/intake_eval.py` (rules vs. model).
- **Public demo mode**: per-visitor data, recorded runs, rate limits, key server-side; Dockerfile and Cloud Run script.
- Page: what the model read, what it dropped, the plan, model calls with time and tokens.

## Limitations (published on purpose)
- The verifier knows five kinds of break; a new kind lands in "not verified" instead of being guessed.
- Relative dates ("yesterday") are not checked against the ledger, because the message date is unknown.
- The intake can still pick the wrong sender when the message itself is ambiguous; the seller sees the sender and the dropped values on the page before sending anything.
- FILL after measuring: the failure cases from the held-out log.
- All data is synthetic (`@example.com`, public test card numbers). On real data, the seller decides whether masked rows may go to Token Factory.

## Feedback on Nebius Token Factory and NVIDIA Nemotron
See [docs/feedback.md](docs/feedback.md) (also pasted in the submission form).

## License
MIT — see [LICENSE](LICENSE).
