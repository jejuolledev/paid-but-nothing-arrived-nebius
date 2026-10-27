"""Assembles the 2-minute submission video: comic panels, the recorded runs, zoomed stills, Zetaris and
Nightshift screens and cards, cut to the narration (docs/demo/vo/N01..N11.wav), with burned-in subtitles
and sponsor badges (rendered by scripts/final_overlays.mjs, since this ffmpeg has no drawtext/subtitles).

Run: node scripts/final_overlays.mjs && python3 scripts/build_final.py   ->  docs/demo/final_v2.mp4
"""
import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "docs/demo"
PARTS, TMP = D / "final_parts", D / "final_parts/_seg"
TMP.mkdir(parents=True, exist_ok=True)
LIVE = next((D / "take_final").glob("page@*.webm"))          # Zetaris + Nightshift run, final code (case 6, then case 5)
CASE5 = LIVE  # the same run continues with case 5 (and a quoted foreign order number)
OFF = next((D / "take_offline").glob("page@*.webm"))          # offline DuckDB run, used for the approve beat
COMIC, ZUI, NUI = D.parent / "comic", D / "zetaris_ui", D / "nightshift_ui"
W, H, FPS, LEAD, GAP = 1920, 1080, 30, 0.25, 0.5
BG = "0x0b0d12"


def run(args):
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *args], capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stderr)


def dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]))


ENC = ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS), "-crf", "18", "-preset", "medium", "-an"]


def still(img, secs, out, zoom=(1.0, 1.06), crop=None):
    """An image (or a crop of one) with a slow push-in."""
    z0, z1 = zoom
    n = max(1, round(secs * FPS))
    pre = f"crop={crop[2]}:{crop[3]}:{crop[0]}:{crop[1]}," if crop else ""
    vf = (f"{pre}scale={W*2}:{H*2}:force_original_aspect_ratio=decrease,pad={W*2}:{H*2}:(ow-iw)/2:(oh-ih)/2:color={BG},"
          f"zoompan=z='{z0}+({z1}-{z0})*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s={W}x{H}:fps={FPS},setsar=1")
    run(["-loop", "1", "-i", str(img), "-vf", vf, "-frames:v", str(n), *ENC, str(out)])


def frame(video, t, out):
    run(["-ss", str(t), "-i", str(video), "-frames:v", "1", str(out)])
    return out


def clip(video, a, b, secs, out, crop=None):
    """Recorded screen from a to b (optionally a 16:9 crop of it), letterboxed; holds the last frame if the slot is longer."""
    hold = max(0.0, secs - (b - a))
    pre = f"crop={crop[2]}:{crop[3]}:{crop[0]}:{crop[1]}," if crop else ""
    vf = (f"fps={FPS},{pre}scale=-2:{H}:flags=lanczos,pad={W}:{H}:(ow-iw)/2:0:color={BG},setsar=1,"
          f"tpad=stop_mode=clone:stop_duration={hold:.3f}")
    run(["-ss", str(a), "-t", str(b - a), "-i", str(video), "-vf", vf, "-t", f"{secs:.3f}", *ENC, str(out)])


LINES = ["N01", "N02", "N03", "N04", "N05", "N05b", "N06", "N07", "N08", "N08b", "N09", "N10", "N11"]
vo = {k: D / "vo" / f"{k}.wav" for k in LINES}
L = {k: dur(p) for k, p in vo.items()}
slot = {k: L[k] + GAP for k in L}
slot["N11"] += 1.5  # title card holds a moment after the last line

f_live_result = frame(LIVE, 155.5, TMP / "live_result.png")        # chain + reply + fix on screen
f_live_sql = frame(LIVE, 159.6, TMP / "live_sql.png")              # a timeline step with its SQL opened
f_live_why = frame(LIVE, 164.6, TMP / "live_why.png")             # Why: per-sentence checks
f_live_rows = frame(LIVE, 170.6, TMP / "live_rows.png")           # the one journey query above the rows
f_status = frame(LIVE, 173.5, TMP / "status.png")                 # "Answered by … Data: Zetaris" + the Nightshift receipt
f_case5 = frame(CASE5, 384.16, TMP / "case5.png")                    # never charged + the refused foreign order
f_zq = ZUI / "30_journey_query_in_zetaris.png"
f_zd = ZUI / "31_three_datasources.png"
CHAIN, REPLYFIX = (240, 0, 960, 540), (240, 250, 960, 540)

# each line: list of (kind, args, seconds or None = fill the rest of the slot[, opts])
PLAN = {
    "N01": [("still", (COMIC / "panel_P1.png",), None)],
    "N02": [("still", (COMIC / "panel_P2.png",), 6.5), ("still", (COMIC / "panel_P3.png",), None)],
    "N03": [("clip", (LIVE, 0.6, 5.9), None, {"crop": (240, 60, 960, 540)})],
    "N04": [("still", (COMIC / "panel_P4.png",), 4.0), ("clip", (LIVE, 152.3, 154.5), 2.2, {"crop": (240, 0, 960, 540)}),
            ("clip", (LIVE, 157.4, 160.8), 3.4, {"crop": (240, 360, 960, 540)}),
            ("still", (f_live_sql,), None, {"crop": (240, 360, 960, 540), "zoom": (1.0, 1.08)})],
    "N05": [("still", (COMIC / "panel_P5.png",), 3.5), ("still", (f_live_result,), 4.5, {"crop": CHAIN}),
            ("clip", (LIVE, 169.6, 171.1), 1.5, {"crop": (240, 0, 960, 540)}),
            ("still", (f_live_rows,), None, {"crop": (240, 0, 960, 540), "zoom": (1.0, 1.06)})],
    "N05b": [("still", (f_live_why,), None, {"crop": (240, 200, 960, 540), "zoom": (1.0, 1.1)})],
    "N06": [("still", (f_live_result,), 6.8, {"crop": REPLYFIX}), ("clip", (LIVE, 173.8, 176.7), None, {"crop": (240, 200, 960, 540)})],
    "N07": [("clip", (OFF, "approve-0.6", "after_fix+0.3"), None, {"crop": (240, 0, 960, 540)})],
    "N08": [("clip", (CASE5, 381.46, 383.96), None, {"crop": (240, 0, 960, 540)})],
    "N08b": [("still", (f_case5,), 2.6, {"crop": (240, 0, 960, 540), "zoom": (1.0, 1.12)}),
             ("still", (f_case5,), None, {"crop": (240, 400, 960, 540), "zoom": (1.0, 1.06)})],
    "N09": [("still", (f_zd,), 3.6, {"crop": (550, 776, 1000, 124)}), ("still", (f_zq,), 3.6, {"crop": (560, 150, 840, 180)}), ("still", (f_zq,), 3.9, {"crop": (550, 776, 1340, 96)}),
            ("still", (NUI / "03_nemotron_lane.png",), 3.6, {"zoom": (1.0, 1.04)}),
            ("still", (f_status,), None, {"crop": (250, 320, 940, 90), "zoom": (1.0, 1.03)})],
    "N10": [("still", (PARTS / "card_measured.png",), None, {"zoom": (1.0, 1.02)})],
    "N11": [("still", (ROOT / "docs/how-it-works.png",), 2.6), ("still", (PARTS / "card_title.png",), None, {"zoom": (1.0, 1.0)})],
}
LIVE_LABEL = {"N03", "N04", "N05", "N05b", "N06", "N08", "N08b"}

off_marks = json.loads((D / "take_offline/marks.json").read_text())


def resolve(v):
    if isinstance(v, str):
        k, _, d = v.replace("-", "+-").partition("+")
        return off_marks[k] + float(d or 0)
    return v


segs, timeline, t = [], [], 0.0
for k, parts in PLAN.items():
    fixed = sum(p[2] for p in parts if p[2])
    for j, p in enumerate(parts):
        kind, args, secs = p[0], p[1], p[2]
        opts = p[3] if len(p) > 3 else {}
        secs = secs or (slot[k] - fixed)
        out = TMP / f"{k}_{j}.mp4"
        if kind == "still":
            still(args[0], secs, out, **opts)
        else:
            v, a, b = args
            a, b = resolve(a), resolve(b)
            clip(v, a, b, secs, out, **opts)
        segs.append(out)
    timeline.append((k, t, slot[k]))
    t += slot[k]

(TMP / "list.txt").write_text("".join(f"file '{s}'\n" for s in segs))
run(["-f", "concat", "-safe", "0", "-i", str(TMP / "list.txt"), *ENC, str(TMP / "body.mp4")])

# overlays: badges throughout, live/offline labels, subtitle strips per line (split lines share time by length)
subs = json.loads((PARTS / "subs.json").read_text())
inputs, filt, last = ["-i", str(TMP / "body.mp4"), "-i", str(PARTS / "badges.png"),
                      "-i", str(PARTS / "label_live.png"), "-i", str(PARTS / "label_offline.png")], [], "0:v"
filt.append(f"[{last}][1:v]overlay=0:0[v1]"); last, n_in = "v1", 4
starts = {k: s for k, s, _ in timeline}
for k, s, d in timeline:
    if k in LIVE_LABEL or k == "N07":
        idx = 2 if k in LIVE_LABEL else 3
        filt.append(f"[{last}][{idx}:v]overlay=0:0:enable='between(t,{s:.3f},{s + d:.3f})'[v{n_in}]"); last = f"v{n_in}"; n_in += 1
for k, s, d in timeline:
    pieces, speak = subs[k], L[k]
    total = sum(len(x) for x in pieces); a = s + LEAD
    for j, txt in enumerate(pieces):
        b = a + speak * len(txt) / total
        inputs += ["-i", str(PARTS / f"sub_{k}_{j}.png")]
        idx = len(inputs) // 2 - 1
        filt.append(f"[{last}][{idx}:v]overlay=0:0:enable='between(t,{a:.3f},{b + (0.3 if j == len(pieces) - 1 else 0):.3f})'[v{n_in}]"); last = f"v{n_in}"; n_in += 1
        a = b
# narration: each line delayed to its slot start
a_in = []
for k, s, _ in timeline:
    inputs += ["-i", str(vo[k])]
    idx = len(inputs) // 2 - 1
    filt.append(f"[{idx}:a]aresample=48000,adelay={int((s + LEAD) * 1000)}:all=1[a{k}]"); a_in.append(f"[a{k}]")
filt.append(f"{''.join(a_in)}amix=inputs={len(a_in)}:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[aout]")
out = D / "final_v2.mp4"
run([*inputs, "-filter_complex", ";".join(filt), "-map", f"[{last}]", "-map", "[aout]",
     "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "19", "-preset", "medium", "-r", str(FPS),
     "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{t:.3f}", "-movflags", "+faststart", str(out)])
json.dump([{"line": k, "start": round(s, 2), "len": round(d, 2)} for k, s, d in timeline], open(TMP / "timeline.json", "w"), indent=1)
print(out, round(t, 1), "s")
