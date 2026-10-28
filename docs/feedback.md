# Feedback: Nebius Token Factory and NVIDIA Nemotron

Written while building this entry, from what actually happened. Logs: `docs/gate_result.json`, `docs/measurements/`; the per-call spend log `build/spend_ledger.jsonl` stays local (git-ignored).
Lines still marked **FILL** are filled after the measurement runs, once credits are on the account.

## What we used them for
- **Nebius Token Factory** (OpenAI-compatible API): every model call at runtime, from a FastAPI server. The key stays on the server.
- **NVIDIA Nemotron, a different model per job:**
  - `nvidia/Nemotron-3.5-Super-VL` reads the customer's payment screenshot.
  - `nvidia/Nemotron-3_5-Lightning` reads the message and plans the read-only lookups.
  - `nvidia/Nemotron-3-Ultra-550b-a55b` re-reads only when code finds the first reading unsure.
  - `nvidia/nemotron-3-super-120b-a12b` writes the cited explanation and the reply.
  - FILL: final per-job choices after the dev runs.

## Bug reports (tool · step · what we did · what happened · expected · suggestion)

### 1. Nemotron 3.5 Super VL: reasoning used the whole token budget, so the answer came back empty
- **What we did (2026-10-28).** One `chat/completions` call to `nvidia/Nemotron-3.5-Super-VL`:
  - one JPEG phone screenshot as an `image_url` data URL
  - a system prompt asking for one JSON object
  - `max_tokens=1200`, `temperature=0`
  - three tries with `response_format` set to `json_schema` strict, then `json_object`, then none
- **What happened.** All three tries used exactly 1,200 completion tokens and returned no JSON. A fourth call with the
  same input, logging the full response, showed why:
  - `finish_reason="length"`
  - `usage.completion_tokens_details.reasoning_tokens=1200`, so every completion token went to reasoning
  - `message.content` was an empty string
  - the image counted 1,202 prompt tokens (`multimodal_tokens.image`)
- The reasoning text in `reasoning_content` had read the screen correctly. It picked the right row (9,900 KRW,
  10/16 05:00, merchant MOAHUB) out of a café charge and an ad, then ran out of tokens before writing the JSON.
- **Expected.** Either reasoning does not count against `max_tokens` on a vision model, or the docs warn that it does.
- **Suggestion.** Two things would have saved us a debugging round:
  - On the model card and in the catalog, say that this model reasons by default and that reasoning counts against
    `max_tokens`. Add one sentence about it to the vision quickstart.
  - Recommend a minimum `max_tokens` for image inputs, or show how to switch reasoning off
    (`chat_template_kwargs.enable_thinking`). FILL: whether `enable_thinking=false` is accepted on Super VL.

### 2. Lightning on the intake prompt: completions stopped at the limit
- **What we saw.** Every intake call on `nvidia/Nemotron-3_5-Lightning` with `max_tokens=1500` reported
  `completion_tokens=1500`, exactly the limit.
- It looks like the same pattern as item 1, but we did not log `finish_reason` on those calls, so this is not
  confirmed. FILL after a rerun that logs `finish_reason`.
- **Suggestion.** On each Nemotron model page, show whether reasoning is on by default and how to change it.

### 3. Sign-up and credits: snags at four steps
- **Contact step.** The e-mail verification code arrives, but the Continue button stays locked until a
  human-verification check passes. The page gives no hint that this is what it is waiting for.
- **Profile step.** It asks for company and "how did you hear about us". That is fine, but it is one more step
  before the first call.
- **Billing step (signing up from South Korea).** Choosing the country clears the address fields that were already
  typed, so they have to be entered again.
- **Promo credits** (`NEBIUS-DEVPOST-GLOBAL26`).
  - The code goes through a HubSpot form and the credit is sent by e-mail later. It is not applied in the console.
  - Until it arrives, the balance is $0 with a card on file, so early test calls go to the card.
  - FILL: hours until the credit arrived.
- **Suggestion.** Apply hackathon codes directly in the billing console, or show "credit pending" so builders know
  whether a call will be charged to their card.

### 4. Two base URLs in the docs, with no word on which to use
- The API reference uses `https://api.tokenfactory.nebius.com/v1/`.
- The code sample on the Nemotron page uses `https://api.tokenfactory.us-central1.nebius.com/v1/`.
- A builder cannot tell whether these are two regions to choose from or the same endpoint. One line would settle
  it: "regional endpoints: …; the default routes to …".

### 5. Model ids are hard to find before signing up
- A public catalog exists (`tokenfactory.nebius.com/api/public/models_info` and `model-catalog.md`). The
  `/v1/models` list for our key matched it: the same five NVIDIA ids.
- But neither the Nemotron page nor the API reference links to that catalog.
- The ids also mix casing: `nvidia/Nemotron-3_5-Lightning`, `nvidia/nemotron-3-super-120b-a12b`,
  `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`.
- **Suggestion.** Link the catalog from the quickstart and keep one id style.

### 6. FILL after the runs
- Structured output (`json_schema`, strict) with an image: honoured, ignored, or a 400?
- p50 and worst latency per model.
- Any 429 or 5xx errors.

## What worked well
- The OpenAI-compatible endpoint: our client needed only a base URL, a key and a model id.
- `/v1/models` answered at once and listed exactly the five NVIDIA ids from the public catalog.
- The usage object breaks out reasoning tokens and image tokens separately. That is how we found bug 1 within
  minutes.

## NVIDIA Nemotron as a model for this job
FILL from the held-out runs:
- Screenshots read right, compared with free on-device OCR + rules (3 of 16).
- Korean messages read right, compared with rules alone (17 of 22).

## Would we build with them again?
FILL: two sentences, after the measurements.
