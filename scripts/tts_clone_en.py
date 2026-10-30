"""Re-voice every narration line from ONE reference line with Qwen3-TTS Base (qwen3-tts-clone, 8191) + Whisper check (8192).
Why (2026-10-30): VoiceDesign with the same seed still drifted per line (median pitch 99-190 Hz), so the narrator
sounded like different people. Cloning from one reference keeps one voice.
  python3 scripts/tts_clone_en.py [REF_ID=P02]   -> docs/video/vo/<id>.wav (old files kept in docs/video/vo_design/)
"""
import base64, difflib, json, os, re, shutil, subprocess, sys, urllib.request, uuid
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
V = ROOT / "docs/video"; VO = V / "vo"; OLD = V / "vo_design"
TTS, STT = "http://127.0.0.1:8191", "http://127.0.0.1:8192"
SAY_NEMOTRON = "Nemo-tron"
REF_ID = sys.argv[1] if len(sys.argv) > 1 else "P02"
LINES = json.loads((V / "lines.json").read_text())["lines"]
norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower().replace("24,900", "24900"))


def pitch(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, np.float32); fr = []
    for i in range(0, len(x) - 1024, 1600):
        s = x[i:i + 1024]
        if np.sqrt((s ** 2).mean()) < 0.02: continue
        c = np.correlate(s, s, "full")[1023:]; lo, hi = 16000 // 300, 16000 // 70
        k = lo + int(np.argmax(c[lo:hi]))
        if c[k] > 0.3 * c[0]: fr.append(16000 / k)
    return float(np.median(fr)) if fr else 0.0


def stt(path):
    b = uuid.uuid4().hex
    data = (f"--{b}\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\nwhisper-large-v3-turbo\r\n"
            f"--{b}\r\nContent-Disposition: form-data; name=\"language\"\r\n\r\nen\r\n"
            f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"a.wav\"\r\nContent-Type: audio/wav\r\n\r\n").encode()
    data += open(path, "rb").read() + f"\r\n--{b}--\r\n".encode()
    req = urllib.request.Request(STT + "/v1/audio/transcriptions", data=data, headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    return json.load(urllib.request.urlopen(req, timeout=120)).get("text", "")


def clone(text, ref_wav, ref_text, out):
    ref = "data:audio/wav;base64," + base64.b64encode(open(ref_wav, "rb").read()).decode()
    body = json.dumps({"model": "qwen3-tts-clone", "input": text, "ref_audio": ref, "ref_text": ref_text, "response_format": "wav"}).encode()
    req = urllib.request.Request(TTS + "/v1/audio/speech", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r, open(out, "wb") as f:
        f.write(r.read())


OLD.mkdir(exist_ok=True)
for p in VO.glob("*.wav"):
    if not (OLD / p.name).exists(): shutil.copy2(p, OLD / p.name)
ref_line = next(l for l in LINES if l["id"] == REF_ID)
ref_wav = OLD / f"{REF_ID}.wav"; ref_text = ref_line["text"].replace("Nemotron", SAY_NEMOTRON)
rf0 = pitch(ref_wav); print("ref", REF_ID, round(rf0), "Hz")
for l in LINES:
    if l["id"] == REF_ID:
        shutil.copy2(ref_wav, VO / f"{REF_ID}.wav"); continue
    best = None
    for k in range(4):
        tmp = VO / f"_{l['id']}_{k}.wav"
        clone(l["text"].replace("Nemotron", SAY_NEMOTRON), ref_wav, ref_text, tmp)
        sc = difflib.SequenceMatcher(None, norm(l["text"]), norm(stt(tmp))).ratio(); f0 = pitch(tmp)
        score = sc - abs(f0 - rf0) / rf0          # words right, and close to the reference pitch
        print(l["id"], k, round(sc, 3), round(f0), "Hz")
        if not best or score > best[0]: best = (score, tmp, sc, f0)
        if sc > 0.97 and abs(f0 - rf0) / rf0 < 0.12: break
    best[1].replace(VO / f"{l['id']}.wav"); print("keep", l["id"], round(best[2], 3), round(best[3]), "Hz")
    for f in VO.glob(f"_{l['id']}_*.wav"): f.unlink()
