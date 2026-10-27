"""English narration for docs/video/lines.json with the local Qwen3-TTS VoiceDesign server (8191) and a Whisper
check (8192) — the same local setup as 로컬llm/video-kit/voice.py, but in English. Free, on this Mac.
Start the servers first (see 로컬llm/video-kit/CLAUDE.md "나레이션"). For each line: N takes, transcribe, keep the take whose
transcript matches the text best (same seed = same voice across lines).

  python3 scripts/tts_en.py            # all lines -> docs/video/vo/N01.wav …
  python3 scripts/tts_en.py N12        # one line again
"""
import difflib, json, os, re, sys, urllib.request, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TTS = os.environ.get("TTS_HOST", "http://127.0.0.1:8191")
STT = os.environ.get("STT_HOST", "http://127.0.0.1:8192")
VOICE = os.environ.get("VOICE", "Calm adult male narrator, clear American English, warm and steady, medium pace")
SEED = int(os.environ.get("VOICE_SEED", "21"))
OUT = ROOT / "docs/video/vo"; OUT.mkdir(parents=True, exist_ok=True)


def tts(text, seed, path):
    body = json.dumps({"model": "qwen3-tts-voicedesign", "input": text, "instructions": VOICE, "voice_seed": seed, "response_format": "wav"}).encode()
    req = urllib.request.Request(TTS + "/v1/audio/speech", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r, open(path, "wb") as f:
        f.write(r.read())


def stt(path):
    b = uuid.uuid4().hex
    data = (f"--{b}\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\nwhisper-large-v3-turbo\r\n"
            f"--{b}\r\nContent-Disposition: form-data; name=\"language\"\r\n\r\nen\r\n"
            f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"a.wav\"\r\nContent-Type: audio/wav\r\n\r\n").encode()
    data += open(path, "rb").read() + f"\r\n--{b}--\r\n".encode()
    req = urllib.request.Request(STT + "/v1/audio/transcriptions", data=data, headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    return json.load(urllib.request.urlopen(req, timeout=120)).get("text", "")


norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower().replace("24,900", "24900"))
lines = json.loads((ROOT / "docs/video/lines.json").read_text())["lines"]
want = set(sys.argv[1:])
for l in lines:
    if want and l["id"] not in want:
        continue
    if l["text"].startswith("FILL"):
        print(l["id"], "skipped: still FILL"); continue
    best = None
    for k in range(3):
        tmp = OUT / f"_{l['id']}_{k}.wav"
        tts(l["text"], SEED, tmp)
        heard = stt(tmp)
        score = difflib.SequenceMatcher(None, norm(l["text"]), norm(heard)).ratio()
        print(l["id"], k, round(score, 3), heard[:90])
        if not best or score > best[0]:
            best = (score, tmp)
        if score > 0.97:
            break
    best[1].replace(OUT / f"{l['id']}.wav")
    for f in OUT.glob(f"_{l['id']}_*.wav"):
        f.unlink()
    print(l["id"], "kept", round(best[0], 3), "(check by ear if < 0.95)")
