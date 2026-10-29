"""Assemble the Nebius demo video from a recorded take (scripts/record_nebius.mjs), the narration wavs
(docs/video/vo/<id>.wav, scripts/tts_en.py) and the rendered cards/subtitles (scripts/video_overlays.mjs).
Every line's picture comes from its "shot" in docs/video/lines.json and the take's marks.json, so nothing here
is a hand-typed timestamp.

  python3 scripts/build_nebius_video.py docs/video/take1 [docs/video/intro1]  ->  docs/video/final_nebius.mp4 (1920x1080, under 3 min)
"intro:a..b" shots come from the screenshot take (scripts/record_proof_intro.mjs), "take:a..b" from the main take.
"""
import json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V = ROOT / "docs/video"
PARTS, TMP = V / "parts", V / "parts/_seg"
TMP.mkdir(parents=True, exist_ok=True)
TAKE = Path(sys.argv[1]) if len(sys.argv) > 1 else V / "take1"
VIDEO = next(TAKE.glob("*.webm"))
MARKS = json.loads((TAKE / "marks.json").read_text())
INTRO = Path(sys.argv[2]) if len(sys.argv) > 2 else V / "intro1"
INTRO_VIDEO = next(INTRO.glob("*.webm"), None) if INTRO.exists() else None
INTRO_MARKS = json.loads((INTRO / "marks.json").read_text()) if INTRO_VIDEO else {}
LINES = json.loads((V / "lines.json").read_text())["lines"]
W, H, FPS, LEAD, GAP = 1920, 1080, 30, 0.25, 0.45
SCREEN_H, SCREEN_Y = 840, 64   # recordings sit below the live badge and above the subtitle band, so neither covers the UI
BG = "0x0b0d12"
ENC = ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS), "-crf", "18", "-preset", "medium", "-an"]


def run(args):
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *args], capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stderr)


def dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]))


def still(img, secs, out, zoom=(1.0, 1.05)):
    n = max(1, round(secs * FPS)); z0, z1 = zoom
    vf = (f"scale={W*2}:{H*2}:force_original_aspect_ratio=decrease,pad={W*2}:{H*2}:(ow-iw)/2:(oh-ih)/2:color={BG},"
          f"zoompan=z='{z0}+({z1}-{z0})*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s={W}x{H}:fps={FPS},setsar=1")
    run(["-loop", "1", "-i", str(img), "-vf", vf, "-frames:v", str(n), *ENC, str(out)])


def clip(a, b, secs, out, video=None, crop=None):
    """Recorded screen from a to b, scaled to 1080p; holds the last frame if the narration is longer,
    speeds up (at most 2x) if the beat is longer than the narration."""
    span = max(0.1, b - a)
    speed = min(4.0, max(1.0, span / secs))   # waits for a model play up to 4x
    hold = max(0.0, secs - span / speed)
    # crop = [x, y, w, h] in the recording's pixels (1440x900): zoom into the part the narration is about
    zoom = (f"crop={crop[2]}:{crop[3]}:{crop[0]}:{crop[1]}," if crop else "")
    vf = (f"setpts=PTS/{speed:.3f},fps={FPS},{zoom}scale=-2:{SCREEN_H}:flags=lanczos,pad={W}:{H}:(ow-iw)/2:{SCREEN_Y}:color={BG},setsar=1,"
          f"tpad=stop_mode=clone:stop_duration={hold:.3f}")
    run(["-ss", f"{a:.3f}", "-t", f"{span:.3f}", "-i", str(video or VIDEO), "-vf", vf, "-t", f"{secs:.3f}", *ENC, str(out)])


def beat(spec, secs, marks=None):
    """'a..b' = from mark a to mark b; 'a' alone = from mark a to the next mark (never into the next beat)."""
    marks = marks or MARKS
    a, _, b = spec.partition("..")
    ta = marks[a]
    later = sorted(v for v in marks.values() if v > ta)
    off = 0.0
    if b and re.search(r"-\d", b):   # "a..b-1.5": end 1.5 s before mark b (e.g. before a scroll starts)
        b, off = b.rsplit("-", 1)[0], float(b.rsplit("-", 1)[1])
    tb = (marks[b] - off) if b else (later[0] if later else ta + secs)
    return ta, tb


vo = {l["id"]: V / "vo" / f"{l['id']}.wav" for l in LINES}
missing = [k for k, p in vo.items() if not p.exists()]
if missing:
    sys.exit(f"missing narration: {missing} (scripts/tts_en.py)")
slot = {k: dur(p) + GAP for k, p in vo.items()}
slot[LINES[-1]["id"]] += 1.5
segs, timeline, t, live = [], [], 0.0, set()
for l in LINES:
    k, shot = l["id"], l["shot"]
    kind, _, arg = shot.partition(":")
    if kind == "card":
        out = TMP / f"{k}.mp4"; still(PARTS / f"card_{arg}.png", slot[k], out); segs.append(out)
    elif kind == "cards":   # several stills, the line's time split evenly (a reveal)
        names = arg.split(",")
        for j, nm in enumerate(names):
            out = TMP / f"{k}_{j}.mp4"; still(PARTS / f"card_{nm}.png", slot[k] / len(names), out, zoom=(1.0, 1.02)); segs.append(out)
    elif kind == "comic":
        panels = arg.split(",")
        for j, pn in enumerate(panels):
            out = TMP / f"{k}_{j}.mp4"; still(ROOT / f"docs/comic/panel_{pn}.png", slot[k] / len(panels), out); segs.append(out)
    elif kind == "intro":
        if not INTRO_VIDEO:
            sys.exit(f"{k}: needs the screenshot take (scripts/record_proof_intro.mjs) in {INTRO}")
        a, b = beat(arg, slot[k], INTRO_MARKS)
        out = TMP / f"{k}.mp4"; clip(a, b, slot[k], out, INTRO_VIDEO, l.get("crop")); segs.append(out); live.add(k)
    elif kind == "take":
        a, b = beat(arg, slot[k])
        out = TMP / f"{k}.mp4"; clip(a, b, slot[k], out, None, l.get("crop")); segs.append(out); live.add(k)
    timeline.append((k, t, slot[k])); t += slot[k]
if t >= 178:
    print(f"WARNING: {t:.1f}s — over the 3-minute rule margin; shorten lines")
(TMP / "list.txt").write_text("".join(f"file '{s}'\n" for s in segs))
run(["-f", "concat", "-safe", "0", "-i", str(TMP / "list.txt"), *ENC, str(TMP / "body.mp4")])

subs = json.loads((PARTS / "subs.json").read_text())
inputs, filt, last, n = ["-i", str(TMP / "body.mp4"), "-i", str(PARTS / "label_live.png")], [], "0:v", 0
for k, s, d in timeline:
    if k in live:
        filt.append(f"[{last}][1:v]overlay=0:0:enable='between(t,{s:.3f},{s + d:.3f})'[v{n}]"); last = f"v{n}"; n += 1
for k, s, d in timeline:
    pieces, speak = subs[k], d - GAP
    total = sum(len(x) for x in pieces); a = s + LEAD
    for j, txt in enumerate(pieces):
        e = a + speak * len(txt) / total
        inputs += ["-i", str(PARTS / f"sub_{k}_{j}.png")]
        idx = len(inputs) // 2 - 1
        tail = 0.25 if j == len(pieces) - 1 else -0.02   # pieces of one line never overlap
        filt.append(f"[{last}][{idx}:v]overlay=0:0:enable='between(t,{a:.3f},{e + tail:.3f})'[v{n}]"); last = f"v{n}"; n += 1
        a = e
a_in = []
for k, s, _ in timeline:
    inputs += ["-i", str(vo[k])]
    idx = len(inputs) // 2 - 1
    filt.append(f"[{idx}:a]aresample=48000,adelay={int((s + LEAD) * 1000)}:all=1[a{k}]"); a_in.append(f"[a{k}]")
filt.append(f"{''.join(a_in)}amix=inputs={len(a_in)}:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[aout]")
out = V / "final_nebius.mp4"
run([*inputs, "-filter_complex", ";".join(filt), "-map", f"[{last}]", "-map", "[aout]",
     "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "19", "-preset", "medium", "-r", str(FPS),
     "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{t:.3f}", "-movflags", "+faststart", str(out)])
json.dump([{"line": k, "start": round(s, 2), "len": round(d, 2)} for k, s, d in timeline], open(V / "timeline.json", "w"), indent=1)
print(out, round(t, 1), "s")
