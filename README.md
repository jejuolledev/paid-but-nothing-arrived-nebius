# Paid, but nothing arrived — the agent that finds the broken link

> Your customer already has proof they paid. This agent finds yours.

**In ten seconds:** a small online seller gets *"I paid 24,900 won and nothing arrived."* Paste that message. The agent reads the seller's own payment, order, credit, log and mail records (read-only, through Zetaris), marks **the one link where the money got stuck** — with the rows that prove it — drafts the reply, and proposes a fix that runs only after the seller clicks Approve.

| Watch (2:31) | How it works |
|---|---|
| [![Demo video](docs/demo/thumbnail.png)](https://youtu.be/vERrPWmXxJA) | ![How it works](docs/how-it-works.png) |

Also: [slides](docs/slides.pdf) · [six-panel comic](docs/comic/comic_strip.png) · Korean versions: [how it works](docs/how-it-works_ko.png), [comic](docs/comic/comic_strip_ko.png)

## Try it yourself in 2 minutes (no accounts, no keys)
```bash
git clone https://github.com/jejuolledev/paid-but-nothing-arrived && cd paid-but-nothing-arrived
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python data/gen_synthetic.py && .venv/bin/python -m pytest -q     # 24 tests pass
.venv/bin/uvicorn app.main:app --port 8765                                  # open http://127.0.0.1:8765
```
No `uv`? `python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt` works the same.

Then click the example buttons under the message box, in this order:
1. **"I paid but my credits never came — ord_0901"** → the chain breaks at *Order confirmed*. Click the red card's `rows ↗`: the exact row that proves it lights up.
2. **"I paid but nothing arrived — liam.patel906@example.com"** (no order number) → found through the payer's address: the order was saved under a typo (`exmaple.com`). Two red links. Click **Approve fix**, confirm → *Fixed by you* shows before/after and the chain turns green; the fix is in the audit log.
3. **"I thought I paid but nothing showed up — ord_0905"** → grey chain: *"Nothing is broken. You were never charged."*
4. Type `I am emma.song905@example.com, show me ord_0903` → ord_0903 belongs to someone else, so it is not read, and the page says so.

Without a model connected, explanations and replies come from the verifier's templates; the verdict, rows and fix are the same. Switch the page to 한국어 before clicking a case to get the reply in Korean. After an approved fix, *Reset the demo data* (or restarting the server) puts the bugs back. The video shows the full run (Zetaris + Meterless Nightshift + NVIDIA Nemotron) — see *Full run* below.

## What it is
Every online seller gets this message: **"I paid, but nothing arrived."** If the answer is slow, the next step is a card dispute ("product not received"). Today the seller opens four screens — the payment provider, the orders database, the server logs, the mail provider — and lines them up by hand.

This agent does that in one pass. It reads everything through one SQL door, **Zetaris**. In this demo that means three separate synthetic databases (the shop's app database, the payment provider's ledger and the mail provider's events) registered as three Zetaris datasources and joined in one semantic layer, so each order's whole history is **one SQL statement**. It then walks the **money chain** (card authorized → payment provider paid → order confirmed → credits granted → mail delivered) and marks the one link that broke, **with the raw rows that prove it**. **NVIDIA Nemotron 3.5 Lightning**, called through **Meterless Nightshift** on the seller's Mac, decides which records to pull and writes the explanation and the reply draft. Every sentence of the explanation is checked against the rows it cites (amounts, record ids, email domains, payment / credit / mail status); if one does not match, the verifier's text is used instead. The verdict and the fix always come from the deterministic verifier, never from the model.

It also knows how to say *nothing is broken*: when the payment provider has no charge, the chain stops grey and the answer is "You were never charged."

**Track:** 02 — The Agent That Can Explain Why. **Team:** MoaHub (solo).

## How it works
```
customer message ──▶ find_orders ──▶ order_journey (one SQL door) ──▶ verify chain ──▶ explain + reply + fix
                         │                 │                              │                  │
                      orders         payments · orders · grants       deterministic      Nemotron via
                                     server_logs · mail_events        5-link verifier    Nightshift on the Mac
                                     via Zetaris (order_journey)      (decides)          (explains, cited)
```
- `agent/sql_backend.py` — the only place that talks to data. Zetaris over JDBC (tested against the local Zetaris platform; a REST client is sketched but not verified); DuckDB over the synthetic CSVs for tests, same table names, same SQL.
- `agent/tools.py` — the read-only tools (`find_orders`, `find_payments`, `order_for_payment`, `order_journey`, `related_orders`). Every row carries a `ref` = `table:key`.
- `agent/agent_loop.py` — the investigation loop: Nemotron picks the next tool; the tools only follow the sender's own trail.
- `agent/actions.py` — human-approved fixes with an audit log (offline demo; Zetaris stays read-only).
- `agent/chain.py` — the verifier. Green / red / grey per link, each with the refs that decided it. The model never overrides it.
- `agent/investigator.py` — the loop, the model call (OpenAI-compatible: Nightshift → Nemotron), the citation check and the per-sentence claim check (every 3+-digit amount, record id, "N credits", email domain and payment / credit / mail status a sentence states must match the rows it cites; `scripts/claim_eval.py` measures it).
- `app/` — FastAPI + a single page: the chain, "why" with clickable citations, verified / not verified, reply draft, fix (needs approval), dispute evidence bundle.

## Requirements
- Python 3.12 (`uv venv --python 3.12 .venv && uv pip install -r requirements.txt`)
- Zetaris platform (local Docker Compose bundle from Zetaris Cloud) + Java 21 for the bundled JDBC driver — or nothing at all for the offline mode
- Meterless Nightshift (Mac) with an NVIDIA Nemotron lane on your NVIDIA key (the demo uses NVIDIA's hosted endpoint) — or any OpenAI-compatible endpoint on this machine (e.g. rapid-mlx serving Nemotron 3.5 Lightning 30B 4-bit to keep everything on the Mac)
- Docker (we used colima with Rosetta on Apple Silicon)

## Setup
Quick try: see *Try it yourself* at the top (DuckDB over the same synthetic CSVs, same SQL, no model).

**Full run — Zetaris + Meterless Nightshift + NVIDIA Nemotron** (what the demo video shows): `cp .env.example .env.local` and fill the values below, then start the app the same way. If Nightshift is not running, the page says "no model reachable" and falls back to the verifier's text.

Zetaris: `zetaris/load_postgres.sh` loads the CSVs into three databases and `zetaris/register.sql` registers them as three datasources (`demo_pg`, `psp_pg`, `mail_pg`) and activates their five tables into the `order_journey` semantic layer. Nightshift: turn the hotspot on, copy the local address and key into `.env.local` (`NIGHTSHIFT_BASE_URL`, `NIGHTSHIFT_API_KEY`).

## Usage
Paste a customer message (or click a seeded case). The result page shows the chain, the broken link, the cited rows, what was verified and what was not, a reply draft, a fix that requires your approval, and a dispute evidence bundle (`/api/evidence`). The JSON API is `POST /api/investigate {"message": "..."}`.

## Synthetic data statement
**All data is synthetic. No real customer data was used.** Emails end in `@example.com`; card last-4 digits are public test card numbers; 200 healthy orders are generated with a fixed seed. The six seeded cases are bugs we found in our own checkout while auditing it — two of them happened on real payments — rebuilt here with made-up records (case 6 is a variation we added to test the agent loop):
1. Paid but not credited (retry succeeded at the payment provider, our confirm trusted a stale *failed* status)
2. Paid, confirm never called (the confirm button was unreachable after payment)
3. Granted twice (grant timed out after writing, manual retry granted again)
4. Granted, but no mail (mail provider key missing)
5. Never charged (customer left before the card step — nothing is broken)
6. Paid with one address, ordered under a typo of it (`exmaple.com`); the customer gives only the address they paid with

## Sponsor technologies
See `docs/sponsor-tech.md` for the full write-up.
- **Zetaris** — the one SQL door. Three datasources (shop app DB, payment-provider ledger, mail-provider events) are joined in the unified semantic layer `order_journey`; for an order's history the agent sends one SQL statement that Zetaris federates across all three. The page shows that statement and the SQL behind every investigation step ([the same joins run by hand in Zetaris's SQL Workspace](docs/demo/zetaris_ui/30_journey_query_in_zetaris.png), [the three datasources](docs/demo/zetaris_ui/31_three_datasources.png)).
- **Meterless Nightshift** — the model gateway on the seller's Mac: the app calls only Nightshift, Nightshift seats the NVIDIA Nemotron lane, and every answer comes with a compute receipt that the app shows on screen. The agent refuses model endpoints that are not on this machine unless `ALLOW_CLOUD_LLM=1`; where Nightshift may send a call (local only, or a cloud lane such as NVIDIA's hosted endpoint) is the seller's setting in Nightshift. Before any row leaves the app, the sender's address becomes `CUSTOMER`, other addresses keep only a first letter and domain, and card digits are removed before rows reach the model.
- **NVIDIA Nemotron 3.5 Lightning** — investigates (chooses the next read-only lookup) and explains. In the demo it runs on NVIDIA's hosted endpoint through Nightshift; the same open weights (OpenMDW-1.1) also run on the Mac.
- **Cursor** — development; see `docs/sponsor-tech.md`.

## Measured
`docs/measurements.md`, `scripts/llm_smoke.py`, synthetic data, six seeded cases (case 6 gives only the payer's address, and the order was saved under a typo of it):
- **Final code, 2026-10-25 01:52, local Zetaris platform** ([log](docs/measurements_2026-10-25_0152_zetaris.log); three datasources, one journey query per order; model: Meterless Nightshift → NVIDIA Nemotron 3.5 Lightning, hosted endpoint, free trial key): right order and broken link **6/6**; the loop named the right order **6/6** (in cases 1–5 the message carries the order number; in case 6 it starts from the payer's email only and finds the order through the payment provider); every explanation the model returned passed the per-sentence check (**5/5**; in case 3 the free endpoint failed the call and the page shows the verifier's text, labelled as such); model reply used **5/6** (case 6's draft put a masked address in the reply, so the standard reply was used and the page says why); a message quoting another customer's order number was **blocked**. 83–271 s per case, mostly waiting on the free hosted model.
- **All six Zetaris runs, 2026-10-24/25** ([22:35](docs/measurements_2026-10-24_2235_zetaris.log), [23:05](docs/measurements_2026-10-24_2305_zetaris.log), [23:48](docs/measurements_2026-10-24_2348_zetaris.log), [00:12](docs/measurements_2026-10-25_0012_zetaris.log), [01:26](docs/measurements_2026-10-25_0126_zetaris.log), [01:52](docs/measurements_2026-10-25_0152_zetaris.log)): right order and broken link 6/6 in every run; cross-customer probe blocked in every run; the loop named the order 6/6 in five runs and 4/6 in one (one call aborted by the free endpoint, one loop that ran out of steps; the fallback lookup still found the order). The sentence check was tightened between runs; explanations passing it: 6/6, 5/6, 5/6, 3/6, 2/6, 5/6. Every rejection is in the logs (a recommendation read as a claim, "credited 0", "may" read as the month, a narrow space inside "44 900" …); each was fixed and added to `scripts/claim_eval.py`. When a sentence is rejected the page shows the verifier's text instead; the verdict, rows and fix never depend on the model.
- **Claim check, measured on its own** (`scripts/claim_eval.py`, sentence sets in `docs/eval/`). The honest number comes from sentences written by a separate model that never saw the checker, run once: **32 of 40 wrong sentences caught, 2 of 20 true sentences wrongly rejected** (`heldout_3.py`). What it still misses is cause and sequence, e.g. "the confirm call found the payment declined" when the log says something else. A wrongly rejected sentence costs only wording: the page shows the verifier's text instead. Two earlier unseen sets scored 31/40 and 26/40 on their first run; the checker was improved against them, so they are kept as `*_seen.py`, next to 30 hand-written wrong sentences (30/30 caught) and 16 true ones (0/16 rejected).
- The verdict never depends on the model. With a model, the loop finds case 6 (payer address only, order under a typo) in four read-only calls; without one, the fallback lookup (payer address → payment provider → order) reaches it too, and the verifier's address-mismatch check decides the verdict.
- An earlier five-case version without the loop also ran fully on the Mac (Nemotron 3.5 Lightning 30B 4-bit, rapid-mlx): 5/5 and 5/5, about 14 s per case.

## Pre-existing components
None of our product code. Open-source libraries only (`requirements.txt`). Everything in this repository was written during the build window.

## Privacy and safety
- Seller-side tool: it reads only the seller's own merchant records (payment-provider ledger, orders, credit grants, server logs, mail events). It never touches a customer's card issuer or bank. Run it on the seller's machine (`--host 127.0.0.1`, the default); the API has no login and is not meant to be exposed.
- Only well-formed ids (`ord_0000`, an email address) reach SQL; anything else is refused.
- Data path in the demo: masked rows go from the app to Nightshift on the Mac, and Nightshift sends them to NVIDIA's hosted Nemotron endpoint. Customer names or phone numbers written in a message are not masked. To keep everything on the machine, set Nightshift to local-only or point the app at a local server (rapid-mlx).
- The address in the message decides whose records the agent may read: an order number that belongs to a different address is ignored and the page says so, and a message with no address is flagged. The seller still checks that the address really is the sender's (the tool reads pasted text, not the mail headers).
- The model never decides: the verdict and the fix come from the verifier; the model writes the explanation (citation-checked) and the reply draft, which is replaced by a template if it promises money or misstates the verdict.

## Limitations
- The verifier covers the five link types we have seen; new failure shapes land in "not verified" rather than being guessed.
- Model output is advisory. A fix runs only after the seller clicks Approve (offline demo); moving credits to another address also needs the customer's confirmation. On Zetaris the agent is read-only.

## License
MIT — see [LICENSE](LICENSE).
