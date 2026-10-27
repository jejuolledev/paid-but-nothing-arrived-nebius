"""On-device OCR (Apple Vision, macOS only, free, no network): the strong baseline for screenshot proof, the source
of the boxes the page draws on the photo, and the redaction step before a photo leaves this machine.

`tools/ocr/ocr_vision.swift` is compiled once into `build/ocr_vision` (git-ignored). On Linux (the public Cloud Run
demo) none of this is available and every caller says so instead of pretending.
"""
from __future__ import annotations
import json, os, platform, shutil, subprocess, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "tools" / "ocr" / "ocr_vision.swift"
BIN = ROOT / "build" / "ocr_vision"


def available() -> bool:
    if os.getenv("OCR_DISABLE") == "1" or platform.system() != "Darwin":
        return False
    if BIN.exists() and (not SRC.exists() or BIN.stat().st_mtime >= SRC.stat().st_mtime):
        return True
    if not shutil.which("swiftc") or not SRC.exists():
        return False
    BIN.parent.mkdir(exist_ok=True)
    r = subprocess.run(["swiftc", "-O", str(SRC), "-o", str(BIN)], capture_output=True, text=True, timeout=600)
    return r.returncode == 0 and BIN.exists()


def ocr_files(paths: list[str | Path], timeout: int = 600) -> list[dict]:
    """One dict per file: {"file", "width", "height", "lines": [{"text", "conf", "box": [x0, y0, x1, y1] px}]}."""
    if not paths:
        return []
    if not available():
        raise RuntimeError("on-device OCR is not available here (macOS Vision only)")
    r = subprocess.run([str(BIN), *map(str, paths)], capture_output=True, text=True, timeout=timeout)
    out = [json.loads(l) for l in r.stdout.splitlines() if l.strip()]
    if len(out) != len(paths):
        raise RuntimeError(f"OCR returned {len(out)} results for {len(paths)} files: {r.stderr[:200]}")
    return out


def ocr_bytes(data: bytes, suffix: str = ".jpg") -> dict:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / ("img" + suffix)
        p.write_bytes(data)
        res = ocr_files([p])[0]
    res.pop("file", None)
    return res


def text_of(ocr: dict) -> str:
    """Lines in reading order (top to bottom, then left to right)."""
    lines = sorted(ocr.get("lines", []), key=lambda l: (round(l["box"][1] / 8), l["box"][0]))
    return "\n".join(l["text"] for l in lines)
