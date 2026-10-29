# Feedback: Nebius Token Factory and NVIDIA Nemotron

Written while building this entry, from what actually happened. Logs: `docs/gate_result.json`, `docs/measurements/`; the per-call spend log `build/spend_ledger.jsonl` stays local (git-ignored).

## What we used them for
- **Nebius Token Factory** (OpenAI-compatible API): every model call at runtime, from a FastAPI server. The key stays on the server.
- **NVIDIA Nemotron, a different model per job:**
  - `nvidia/Nemotron-3.5-Super-VL` reads the customer's payment screenshot.
  - `nvidia/Nemotron-3_5-Lightning` reads the message, plans the read-only lookups and, in the second turn, reads the customer's answer.
  - `nvidia/Nemotron-3-Ultra-550b-a55b` re-reads only when code finds the first reading unsure.
  - `nvidia/nemotron-3-super-120b-a12b` writes the cited explanation and the reply.
  - Kept after the dev runs: reasoning off for the two readers (vision, intake), on (model default) for the writer.

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
    (`chat_template_kwargs.enable_thinking`). We confirmed on 2026-10-29: `enable_thinking=false` is accepted on Super VL. With it, the same
    photo came back as a correct strict-JSON answer in 146 completion tokens. Over the 16 held-out photos: average 5.5 s, none
    empty. One later call (OCR-text input, no image) still used all 4,000 tokens and returned nothing (`finish_reason=length`).

### 2. Lightning on the intake prompt: completions stopped at the limit
- **What we saw.** Every intake call on `nvidia/Nemotron-3_5-Lightning` with `max_tokens=1500` reported
  `completion_tokens=1500`, exactly the limit.
- It looks like the same pattern as item 1, but we did not log `finish_reason` on those calls, so this is not
  confirmed. With `enable_thinking=false` the same intake prompt used at most 411 completion tokens over 113 calls,
  median 2.0 s, so reasoning was the cause.
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
  - The credit had not arrived about 30 hours after the promo request (2026-10-28 to 10-29), and other
    participants in the Discord channel reported the same. We asked support and Discord. We ran the whole
    measurement and recording on the card (about $0.9 in total, by our per-call ledger).
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

### 6. What we measured about the endpoint (2026-10-29, about 570 calls)
- Structured output (`json_schema`, strict) with an image: honoured on Super VL (every answer parsed against the schema).
- Median and worst latency per call: Super VL 4.2 s / 55 s (the 55 s call ran to 4,000 tokens; the first dev run of
  the day averaged 27 s per photo, later runs 3-6 s); Lightning 2.0 s / 5.5 s; Ultra 2.5 s / 17 s; Super 6.9 s / 26 s.
- One failed call in the 40-message run (we did not keep its error type); two calls ran to the 4,000-token limit (a Super VL
  call on OCR-text input, which returned nothing, and one Ultra re-read); no other failures.
- There is no usage or balance endpoint in the API (`/v1/usage`, `/v1/balance` and similar return 404), so we
  kept our own per-call ledger from the `usage` object and catalog prices. A usage endpoint would let builders
  set a hard budget in code.

## What worked well
- The OpenAI-compatible endpoint: our client needed only a base URL, a key and a model id.
- `/v1/models` answered at once and listed exactly the five NVIDIA ids from the public catalog.
- The usage object breaks out reasoning tokens and image tokens separately. That is how we found bug 1 within
  minutes.

## NVIDIA Nemotron as a model for this job
From the held-out runs (run once each):
- Screenshots: Super VL read the payment and reached the right verdict on 14 of 16 phone photos; free on-device OCR +
  payment-word rules 3 of 16. Given only the OCR text, the same model got 13 of 16: its strength here is picking
  the right line out of a crowded screen (balances, running totals, ads, other rows). Its two misses: it took a
  running total for the payment once, and did not recognise an unfinished checkout once.
- Korean messages: Lightning (with Ultra when unsure) found who was writing on 20 of 22, rules 16 of 22. Lightning
  asked for Ultra on 16 of 22 Korean threads, so Ultra did much of the work there.

## Would we build with them again?
Yes. One OpenAI-compatible endpoint with a vision model and three text models let us give each job its own model
with one environment variable, and the usage object told us exactly where the tokens went. What we would ask for:
reasoning defaults on the model cards, promo credits applied in the console, and a usage endpoint.
