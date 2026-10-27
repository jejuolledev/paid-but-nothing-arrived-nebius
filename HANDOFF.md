# HANDOFF — what is left once the Token Factory key exists

Deadline: **Sat 2026-10-31 02:00 KST** (Fri Oct 30 10:00 PDT). Aim to press Submit by **10/30 22:00 KST**.
Everything below runs in `/Users/ollekil/Desktop/Moahub-Labs/hackathons/paid-but-nothing-arrived-nebius`.
Headless only; no paid services beyond the free Token Factory credits; nothing is published without the owner's yes.

Already done (no key needed): code, 38 tests, public demo mode, rules-only baseline on the held-out set
(38/40), recorder/video/TTS scripts (dry-run tested with the FAKE stand-in), Dockerfile + Cloud Run script,
README / feedback / form drafts with FILL marks.

## 0. Owner: sign up and get the key (owner, 15–30 min)
1. Devpost: make sure you have joined the hackathon (nebiusglobalaihackathon.devpost.com → "Join hackathon").
2. Nebius Token Factory sign-up (tokenfactory.nebius.com). **Write down anything that goes wrong** (country list,
   card step, email) — it goes into the feedback section. If Korea is missing from the billing country list: Nebius
   Discord (discord.gg/eXYTGhgnhK), Devpost Global AI Hackathon channel (FAQ says case by case).
3. Credits: nebius.com/promo-code with code `NEBIUS-DEVPOST-GLOBAL26`; and dev.nebius.com/builders (Builder Program).
   Note how long each took.
4. Create an API key and put it in `.env.local` (this file is git-ignored):
   ```
   cp .env.example .env.local     # then edit: NEBIUS_API_KEY=...
   ```

## 1. First call and model ids (Claude, 10 min)
```bash
.venv/bin/python scripts/tf_models.py          # lists NVIDIA ids your key can call -> docs/token_factory_models.json
.venv/bin/python scripts/tf_smoke.py           # hello + one intake call with the default nvidia/nemotron-3-super-120b-a12b
```
- If the Super id is not in the list, use the listed Nemotron Super/Nano id in `.env.local` (`LLM_MODEL=`).
- If replies are empty or slow because of reasoning: try `LLM_EXTRA_BODY={"chat_template_kwargs": {"enable_thinking": false}}`
  and run the smoke again. Record what happened (feedback "Reasoning output format").
- If a model returns 400 on `temperature`/`max_tokens`, note it, adjust `agent/llm.py`, rerun tests.

## 2. Dev set: tune only here (Claude, 15–30 min)
```bash
.venv/bin/python scripts/intake_eval.py --set dev --mode model
.venv/bin/python scripts/intake_eval.py --set dev --mode model --model <a Nano id>   # optional: is the small one enough?
```
Change the prompt in `agent/intake.py` only from dev-set failures. Then `.venv/bin/python -m pytest -q`.
Pick per-step models (e.g. intake = Super, explain = Super or Nano) by accuracy first, then time.

## 3. Held-out set: report, once (Claude, 10 min)
```bash
.venv/bin/python scripts/intake_eval.py --set heldout --mode model
.venv/bin/python scripts/llm_smoke.py           # six seeded cases end to end, appends to docs/measurements.md
git add docs/measurements* && git commit -m "Held-out run on Token Factory: <numbers>"
```
Do not tune on held-out failures after this run; list them in README Limitations instead.

## 4. Fill the numbers (Claude, 20 min)
- `README.md`: Measured table (`FILL`, `MODEL_ID`), what the model still misses, Limitations.
- `docs/video/measured.json` and line N12 in `docs/video/lines.json`.
- `docs/feedback.md`: every FILL from what actually happened in steps 0–3.
- `docs/submission_form.md`: FILL numbers, model ids.
Check: `grep -rn "FILL\|TRY_IT_URL\|VIDEO_URL\|REPO_URL\|MODEL_ID" README.md docs/*.md docs/video/*.json`

## 5. Recorded runs for the public demo (Claude, 5 min)
```bash
.venv/bin/python scripts/precompute.py          # data/precomputed/case1..6.json, each "status": "ok"
```
Rerun if any status is not ok. Commit them.

## 6. Record the walkthrough (Claude, 10 min)
```bash
.venv/bin/uvicorn app.main:app --port 8765 &    # local mode, real key
node scripts/record_nebius.mjs http://127.0.0.1:8765 docs/video/take1
```
If it prints "WARNING: a model call failed", record again. Look at a few frames (ffmpeg -ss … -frames:v 1).

## 7. Narration and video (Claude, 40–60 min)
```bash
# start the local TTS (8191) and Whisper (8192) servers as in 로컬llm/video-kit/CLAUDE.md "나레이션"
python3 scripts/tts_en.py
TRY_URL=<cloud run url or leave for now> node scripts/video_overlays.mjs
python3 scripts/build_nebius_video.py docs/video/take1      # -> docs/video/final_nebius.mp4
```
Check length < 2:55, frames at each line, transcript vs lines.json, "Nemotron" and "Token Factory" said aloud.
Owner: upload to YouTube **public**, title "Paid, but nothing arrived — Nemotron on Nebius Token Factory". (10 min)

## 8. Deploy the public demo (owner approves; then 15 min)
Uses the existing Google Cloud project `storymoa` (billing on; Run, Cloud Build, Artifact Registry already enabled).
One service, 0–1 instance, so it stays in the free tier; it costs nothing while idle.
```bash
PROJECT=storymoa REGION=us-central1 bash deploy/cloudrun.sh
```
Then from this Mac: open the URL headless, click example 6, "Run it live now", Approve, Reset; `curl <url>/api/health`.
Keep it running until Dec 15 (judging end).

## 9. Publish the repository (owner approves; 5 min)
```bash
git status   # clean; .env.local must NOT be listed by: git ls-files | grep env
gh repo create jejuolledev/paid-but-nothing-arrived-nebius --public --source . --push \
  --description "Nemotron on Nebius Token Factory reads 'I paid but nothing arrived' messages; a verifier finds where the money got stuck."
```
Check the repo page shows "MIT license" in About. Replace REPO_URL / TRY_IT_URL / VIDEO_URL in README and push.
**Never touch github.com/jejuolledev/paid-but-nothing-arrived** (frozen for the Open Agent judging, results 11/6).

## 10. Devpost form (Claude fills in Chrome, owner presses Submit; 30 min)
Values: `docs/submission_form.md` (code blocks). Feedback: `docs/feedback.md`. Thumbnail: a frame of the result page.
Owner presses **Submit** before 10/31 02:00 KST.

## Time if nothing breaks
Steps 1–7 about 2.5–3 hours of Claude time; owner time about 1 hour (sign-up, YouTube, two approvals, Submit).
