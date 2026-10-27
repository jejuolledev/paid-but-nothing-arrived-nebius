# Feedback: Nebius Token Factory and NVIDIA Nemotron

Written while building this entry. Only things we actually ran into; sections marked **FILL** are filled in on the
day of signup and measurement (2026-10-28), from what really happens, not before.

## What we used them for
- **Nebius Token Factory** (OpenAI-compatible API) — every model call at runtime: reading the customer's message and
  planning the lookups, then writing the cited explanation and reply. Called from a FastAPI server; the key stays
  on the server.
- **NVIDIA Nemotron** — FILL: exact model id(s) used per step, and why (e.g. Super for reading/planning, Nano for …).

## Onboarding (zero to first call)
- Signing up from Korea: FILL (did Korea appear in the billing / country list? any blocker?).
- Promo credit code `NEBIUS-DEVPOST-GLOBAL26` and Builder Program credits: FILL (how long until credits showed up).
- Time from account to first successful `chat/completions`: FILL minutes.

## What worked well
- OpenAI-compatible endpoint: our client code needed only a base URL, a key and a model id; the same code ran
  against a local server and Token Factory. FILL: confirm after first run.
- FILL: latency and token use we measured (from `docs/measurements_nebius.md`).

## What needs work (specific)
- **Two base URLs in the docs, no word on which to use.** The API reference examples use
  `https://api.tokenfactory.nebius.com/v1/`, while the code sample on the Nemotron page
  (nebius.com/services/token-factory/nemotron) uses `https://api.tokenfactory.us-central1.nebius.com/v1/`.
  A builder can't tell whether these are regions to choose between, the same thing, or one being replaced.
  A one-line note ("regional endpoints: …; the default routes to …") would settle it.
- **Exact Nemotron model ids are hard to find before signing up.** The Nemotron page lists four models
  (Nano 30B, Nano Omni, Super 120B, Ultra 550B) but shows an API id only for Super
  (`nvidia/nemotron-3-super-120b-a12b`, inside a code sample). The docs overview page we fetched names no model ids.
  `/v1/models` needs a key. Third-party catalogs list ids with mixed casing (`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`
  vs `nvidia/nemotron-3-super-120b-a12b`), so we could not plan per-step model choice until after signup.
  Suggestion: a public table of model id, context length, price, and whether it is a reasoning model.
- **Reasoning output format.** FILL: whether Nemotron answers came wrapped in `<think>…</think>`, in
  `reasoning_content`, or plain; whether `chat_template_kwargs` / `reasoning_effort` were accepted. (Our client
  strips `<think>` and falls back to `reasoning_content`; tell us what you saw.)
- FILL: JSON-only adherence for the intake prompt (how often the reply was not a single JSON object).
- FILL: any rate limit or error we hit, with the exact message.

## NVIDIA Nemotron as a model for this job
- FILL from the held-out run: what it got right that rules miss (sender among several addresses, the shop's own
  address in a forwarded mail, Korean amounts), and where it still failed (ids from the log).

## Would we build with them again?
FILL: yes / no and why, in two sentences, after the measurements.
