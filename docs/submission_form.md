# Devpost submission — Nebius × NVIDIA Global AI Hackathon

Deadline: **Fri Oct 30, 2026 10:00 PDT = Sat Oct 31 02:00 KST**. Submit a few hours early.
Before pasting: replace every `FILL` / `TRY_IT_URL` / `VIDEO_URL` / `REPO_URL` (HANDOFF.md step 9 checks this).
The exact hackathon-specific questions are only visible after "Enter a submission"; the usual Devpost fields are
below, plus the ones the rules require (track, feedback, what changed during the period, repo, demo URL, video).

## Project name
```
Paid, but nothing arrived
```

## Elevator pitch (≤200 characters)
```
A seller pastes "I paid but nothing arrived." Nemotron on Nebius Token Factory reads who wrote and what they claim; a verifier finds where the money got stuck, with the rows that prove it.
```

## Track
```
Best Apps and Agents
```

## Built with
```
nvidia-nemotron, nebius-token-factory, python, fastapi, duckdb, openai-python, google-cloud-run, playwright
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
I run a small online shop in Korea. The message I dread most is "I paid 24,900 won and nothing arrived." Answer slowly and it becomes a card dispute. The answer is spread across the payment provider, our orders database, the server logs and the mail provider. The six example cases in the demo are bugs I found in my own checkout (two happened on real payments), rebuilt with synthetic data.

## What it does
Paste the customer's message. NVIDIA Nemotron, running on Nebius Token Factory, reads it first: which address is the customer's own (not the spouse's, not a CC, not the shop's own address in a forwarded mail), what they claim (amount, when, which pack, what went wrong), whether they ask for someone else's order, and a short plan of read-only lookups. The plan runs only on the sender's own trail. A rule-based verifier then walks the money chain (card authorized → payment provider paid → order confirmed → credits granted → mail delivered) and marks the one broken link, with the rows that prove it. Nemotron writes the explanation and a reply in the customer's language; every sentence is checked against the rows it cites. The fix runs only after the seller clicks Approve.

The page also shows what the customer says vs. what the records show, what the model read and what it got dropped for, and what plain rules would have found without the model.

## How we built it
- Token Factory through its OpenAI-compatible API: two Nemotron calls per message (read + plan, then explain + reply), each logged with model, time and tokens on the page.
- Before the model sees the message, addresses become EMAIL_1, EMAIL_2 (first letter + domain) and card digits are removed. After it answers, code keeps only values the message actually states (amounts in digits, 만/천 units or Korean number words) and drops the rest, visibly.
- The verdict and the fix never come from the model.
- Public demo: per-visitor copy of the synthetic data, recorded live runs for the example buttons (with a "Run it live now" button), rate limits, the key only on the server.

## Measured
On 40 messy messages written by a separate model that never saw our prompt or code (committed before the first model run): right order and broken link FILL/40 with Nemotron reading the message, 38/40 with rules only; complaint read correctly FILL/40; FILL values dropped as unsupported. Average model time per message FILL ms. 38 automated tests.

## Challenges
FILL (real ones from the build: e.g. reasoning output format, JSON adherence, latency for a public demo).

## What's next
Connect it to a real payment provider's API and a shop database in read-only mode, and add the next kinds of break we see in our own shop.
```

## How was the project significantly updated during the Submission Period? (required for existing projects)
```
The project was first written on Oct 22–25, 2026 (inside this hackathon's submission period) for another event, the Open Agent Hackathon, where it ran on a local data platform and NVIDIA's own hosted Nemotron endpoint. That version is frozen at tag submitted-2026-10-25 in github.com/jejuolledev/paid-but-nothing-arrived. This entry is a separate repository whose first commit is that snapshot. Added for this hackathon (Oct 27–30, see git log): every model call now runs on Nebius Token Factory; a new Nemotron step that reads the customer's message and plans the lookups, with grounding and a sender-scoped plan (before, a regex took the first address and order number); customer claims vs. records; a 40-message held-out evaluation (rules vs. model); and a public demo mode (per-visitor data, recorded runs, rate limits).
```

## Which NVIDIA models and where did Token Factory help?
```
FILL model ids. Token Factory runs both model steps at runtime: reading + planning (LLM_MODEL_INTAKE) and the cited explanation + reply (LLM_MODEL_EXPLAIN). Being OpenAI-compatible, it dropped into our existing client with a base URL and key; we used FILL to compare models on the same held-out set in one afternoon.
```

## Feedback on Nebius Token Factory, AI Cloud and NVIDIA tools (required)
Paste docs/feedback.md (after filling it), as plain text.

## Testing instructions (for judges)
```
Open TRY_IT_URL. No login. Click an example under the message box — the six examples answer at once from a recorded live run on Token Factory (labelled, with the time); press "Run it live now" to call Nemotron for real (about FILL seconds). Best first click: "Two addresses" (example 6): the rules-only line shows what plain rules would have found. Approve the fix, and the chain turns green; your changes affect only your own copy of the data. Any message you type runs live (limited to 8 live runs per hour per visitor; after that the verifier answers without the model and says so). All data is synthetic.
```
