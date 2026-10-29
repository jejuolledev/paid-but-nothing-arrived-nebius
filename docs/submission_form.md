# Devpost submission — Nebius × NVIDIA Global AI Hackathon

Deadline: **Fri Oct 30, 2026 10:00 PDT = Sat Oct 31 02:00 KST**. Submit a few hours early.
Before pasting: replace `TRY_IT_URL` / `VIDEO_URL` / `REPO_URL` (owner steps).
The exact hackathon-specific questions are only visible after "Enter a submission"; the usual Devpost fields are
below, plus the ones the rules require (track, feedback, what changed during the period, repo, demo URL, video).

## Project name
```
Paid, but nothing arrived
```

## Elevator pitch (≤200 characters)
```
"I paid, here's my screenshot." Nemotron VL reads the banking-app photo, the payment ledger checks it, and the money chain shows where it got stuck. Edit the amount or time: the ledger never saw it.
```

## Track
```
Best Apps and Agents
```

## Built with
```
nebius-token-factory, nvidia-nemotron, nemotron-3.5-super-vl, nemotron-3.5-lightning, nemotron-3-ultra, nemotron-3-super-120b, python, fastapi, duckdb, openai-python, playwright, google-cloud-run
```

## Try it out (links)
```
TRY_IT_URL
REPO_URL
```

## Video demo link
```
VIDEO_URL
```

## About the project (markdown)
```
## Inspiration
I run a small online shop in Korea. The message I dread most is "I paid 24,900 won and nothing arrived". The proof a customer can attach is a phone photo of their banking app. Answer slowly and it becomes a card dispute. Banks in the Philippines (BDO) and Indonesia (BCA) have publicly warned about fake proof-of-payment screenshots; the advice is to check your own records, not the picture. The answer is spread across the payment provider, our orders database, the server logs and the mail provider. Five of the six example message cases are bugs from my own checkout (two hit real payments), rebuilt with synthetic data; the sixth is a variation.

## What it does
Drop in the customer's screenshot and message. Nemotron 3.5 Super VL on Nebius Token Factory reads the photo (the payment line, not the balance, points, the phone's clock or the yen conversion) and, where on-device OCR can locate them, the numbers it read light up on the photo. The payment provider's ledger checks them: same amount, within ten minutes, same card when the screen shows one. Then a five-link money chain (card, payment provider, order, credits, e-mail) shows the one link where the money got stuck, citing the rows. Nemotron writes the reply in the customer's language (Korean, Japanese, English); the fix runs only after the seller clicks Approve.

Edit the amount, date or time on a screenshot and the ledger has never seen that payment: the page says so and the reply politely asks for the card-statement line. The model does not detect the edit; the ledger does. And sometimes the honest answer is "Nothing is broken. You were never charged."

## How we built it
- A different Nemotron per job, all on Token Factory through its OpenAI-compatible API: Super VL reads the photo; Lightning reads the message and plans read-only lookups; Ultra re-reads only when code finds the first reading unsure; Super writes the cited explanation and reply. Each call's model, time, tokens and cost are on the page.
- Before anything leaves the app: photo metadata removed and resized (on a Mac, e-mail addresses and long numbers blurred with on-device OCR); addresses in the message become EMAIL_1, EMAIL_2; card digits removed.
- Code checks everything the models return: a value not supported by the photo or message is dropped and shown; every explanation sentence is checked against the rows it cites; the verdict and the fix never come from a model.
- Public demo: per-visitor copy of the synthetic data, recorded live runs for the examples ("Run it live now" for a real call), rate limits, the key only on the server.

## Measured (held-out sets built by a separate agent before any model run)
- 16 phone photos (Korean, Japanese; 8 edited), run once: payment read right and verdict right — Nemotron 3.5 Super VL 14/16; free on-device OCR + payment-word rules 3/16. Given only the OCR text, the same Nemotron gets 13/16, so most of the gain is choosing the right line on a crowded screen. Edited screenshots: 8/8 "not in the ledger" with Nemotron reading the image; the ledger, not the reader, rejects them.
- 22 Korean-heavy messages, run once: who is writing — Nemotron 20/22, rules 16/22; right order and broken link — Nemotron 20/22, rules 21/22. One of Nemotron's two misses is a prompt-injection message where it named no sender, so nobody's records were read.
- 40 English-heavy messages: Nemotron 40/40, rules 38/40.
- Cost and time: about 5.5 s and $0.0008 per photo read; a full photo case (read, plan, explain, reply) took 10-16 s in our recorded runs.

## Limitations
- The photo set is synthetic (rendered app screens, photographed-looking distortions); not yet measured on real customer photos.
- The model cannot tell an edited screenshot from a real one; only the ledger can.
- The verifier knows five kinds of break; a new kind lands in "not verified".

## Challenges
Nemotron 3.5 Super VL spent its whole token budget reasoning on the first gate run (the reasoning had read the screen correctly; the answer was empty). Turning reasoning off for the two reader jobs (chat_template_kwargs.enable_thinking=false, accepted on Super VL and Lightning) fixed it: answers in about 5 s, no empty replies.

## What's next
Connect it read-only to a real payment provider's API and a shop database; English and more banking-app layouts.
```

## How was the project significantly updated during the Submission Period? (required for existing projects)
```
First written on Oct 22-25, 2026 (inside this hackathon's submission period) for the Open Agent Hackathon, where it read text messages only, on a local data platform and NVIDIA's hosted endpoint; frozen at tag submitted-2026-10-25 of github.com/jejuolledev/paid-but-nothing-arrived. This entry is a separate repository whose first commit is that snapshot. Added for this hackathon (Oct 27-30, see git log): screenshot proof (Nemotron 3.5 Super VL reads the photo, the ledger decides, edited screenshots are caught by the ledger); a different Nemotron per job on Nebius Token Factory with an Ultra re-read only when unsure, and cost per call; a Nemotron step that reads the message and plans the lookups (before, a regex); Japanese replies (Korean existed before); two held-out sets built before any model run (16 phone photos, 22 Korean-heavy messages) with free OCR and rules baselines; a public demo mode.
```

## Which NVIDIA models and where did Token Factory help?
```
nvidia/Nemotron-3.5-Super-VL reads the customer's payment screenshot; nvidia/Nemotron-3_5-Lightning reads the message and plans the lookups; nvidia/Nemotron-3-Ultra-550b-a55b re-reads only when the first reading is unsure; nvidia/nemotron-3-super-120b-a12b writes the cited explanation and the reply. Token Factory serves all four behind one OpenAI-compatible endpoint, so routing each job to a different model is one environment variable per job; the page shows the model, time, tokens and cost of each call. Measured: about $0.0008 and 5.5 s per photo read; a full case costs well under one cent.
```

## Feedback on Nebius Token Factory, AI Cloud and NVIDIA tools (required)
Paste docs/feedback.md (after filling it), as plain text.

## Testing instructions (for judges)
```
Open TRY_IT_URL. No login. Best first click: "Or try a customer's screenshot" -> "Korean card SMS, 9,900 won": the photo, the numbers Nemotron read, photo vs ledger, then the money chain. Then "Card alert with its date edited": the ledger has never seen that payment. Examples answer at once from a recorded live run on Token Factory (labelled, with the time); "Run it live now" calls Nemotron for real (about 10-16 seconds). You can also drop or paste (Ctrl/Cmd+V) your own screenshot; it is not stored. Message examples are below the box; Approve a fix and the chain turns green, in your own copy of the data only. Live runs are limited to 4 per hour per visitor and 10 per day in total; after that the ledger and verifier still answer and the page says no model was used. All data is synthetic.
```
