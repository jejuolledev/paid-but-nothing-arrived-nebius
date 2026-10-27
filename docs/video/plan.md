# Video plan — Nebius × NVIDIA (under 3:00, English, YouTube public)

Rules that shape it: under 3 minutes (judges stop at 3:00); must show the app working; no third-party trademarks
or copyrighted music (so: **no music**, narration only); name Token Factory and the Nemotron model **out loud**
("with audio, not a passing mention" — Devpost update "How to build a winning project"); judges' advice
("Will It Ship?"): aha in 30 seconds, show which model does what, publish limitations.

Target length about 2:20 (13 lines, `docs/video/lines.json`). Aha by 0:35: the two-address message, the model
picks the payer, the rules-only line says what plain rules would have found.

| # | Picture (shot in lines.json) | Narration (short) |
|---|---|---|
| N01 | card: customer message | "I paid 24,900 won and nothing arrived." … chargeback |
| N02 | comic panels P2, P3 | four places to look |
| N03 | take: typing the two-address message → Investigate | wife's address vs. the one he paid with |
| N04 | take: "What Nemotron read" card, masked text open | Nemotron on Nebius Token Factory reads first; addresses hidden; unsupported values dropped |
| N05 | take: yellow rules-only line | a simple rule finds nothing |
| N06 | take: planned lookups timeline | read-only, sender's own trail |
| N07 | take: headline + chain → click red link → rows | verifier, not the model; typo `exmaple.com`; rows cited |
| N08 | take: claims vs records | amount matches |
| N09 | take: model calls table (model id, time, tokens) | two Nemotron calls on Token Factory |
| N10 | take: Approve → green | fix runs; public demo = your own copy |
| N11 | take: case 5 with a friend's order number | not read; never charged |
| N12 | card: measured (docs/video/measured.json) | the held-out numbers, rules vs. model — FILL after measuring |
| N13 | card: title + try-it link | "Found in one pass." |

Pipeline (all headless, free, on this Mac):
1. `node scripts/record_nebius.mjs http://127.0.0.1:8765 docs/video/take1` (local server with the real key; it resets the demo data first)
2. `python3 scripts/tts_en.py` (local Qwen3-TTS + Whisper check; servers from 로컬llm/video-kit) → `docs/video/vo/N01..N13.wav`
3. `TRY_URL=<url> node scripts/video_overlays.mjs` → subtitles, cards
4. `python3 scripts/build_nebius_video.py docs/video/take1` → `docs/video/final_nebius.mp4`
5. Check: length < 2:55; frames at each line start; Whisper transcript of the final audio matches lines.json; no FAKE label anywhere.

Optional 3-second shot: the Token Factory console usage page rising after a run (owner's screenshot; it needs a
logged-in browser, so Claude does not take it). Without it, the on-page "Model calls" table already shows the model
id, provider, time and tokens of each real call.
