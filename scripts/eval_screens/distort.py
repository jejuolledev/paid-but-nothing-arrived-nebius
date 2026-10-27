"""Phone-photo distortions and crude-edit compositing (PIL + numpy, seeded).

Every function takes an explicit numpy Generator so the whole set is reproducible.
"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps


# ---------------------------------------------------------------- doctoring
def crude_paste(orig: Image.Image, edit: Image.Image, box, rng, recipe: dict) -> tuple[Image.Image, list]:
    """Paste the region of `edit` that differs from `orig` (inside `box`) onto `orig`.

    recipe keys: pad (px), tone (int added to RGB of the patch), jpeg_q (patch re-save
    quality or None), alias (bool, hard-threshold the text edges), dx/dy (patch offset px).
    Returns (image, patch_box).
    """
    a = np.asarray(orig.convert("RGB")).astype(np.int16)
    b = np.asarray(edit.convert("RGB")).astype(np.int16)
    x0, y0, x1, y1 = box
    diff = np.abs(a[y0:y1, x0:x1] - b[y0:y1, x0:x1]).sum(axis=2) > 24
    ys, xs = np.nonzero(diff)
    if len(xs) == 0:
        raise ValueError("edit render does not differ from original inside box")
    pad = recipe.get("pad", 4)
    px0 = max(0, x0 + xs.min() - pad)
    py0 = max(0, y0 + ys.min() - pad)
    px1 = min(a.shape[1], x0 + xs.max() + pad + 1)
    py1 = min(a.shape[0], y0 + ys.max() + pad + 1)
    patch = edit.convert("RGB").crop((px0, py0, px1, py1))
    if recipe.get("alias"):
        # hard edges like text typed in a basic photo editor without antialiasing
        g = np.asarray(patch).astype(np.int16)
        bg = np.median(g.reshape(-1, 3), axis=0)
        dist = np.abs(g - bg).sum(axis=2)
        fg = g[dist == dist.max()][0] if dist.max() > 0 else bg
        mask = dist > dist.max() * 0.45
        g = np.where(mask[..., None], fg, bg)
        patch = Image.fromarray(g.astype(np.uint8))
    tone = recipe.get("tone", 0)
    if tone:
        g = np.asarray(patch).astype(np.int16) + tone
        patch = Image.fromarray(np.clip(g, 0, 255).astype(np.uint8))
    q = recipe.get("jpeg_q")
    if q:
        buf = io.BytesIO()
        patch.save(buf, "JPEG", quality=q)
        patch = Image.open(io.BytesIO(buf.getvalue())).convert("RGB")
    out = orig.convert("RGB").copy()
    out.paste(patch, (px0 + recipe.get("dx", 0), py0 + recipe.get("dy", 0)))
    if recipe.get("region_jpeg_q"):
        # re-save a wider area around the patch, as when the editor exported a crop
        m = 40
        rb = (max(0, px0 - m), max(0, py0 - m), min(out.width, px1 + m), min(out.height, py1 + m))
        reg = out.crop(rb)
        buf = io.BytesIO()
        reg.save(buf, "JPEG", quality=recipe["region_jpeg_q"])
        out.paste(Image.open(io.BytesIO(buf.getvalue())).convert("RGB"), rb[:2])
    return out, [int(px0), int(py0), int(px1), int(py1)]


# ---------------------------------------------------------------- photo look
def _jpeg(img: Image.Image, q: int) -> Image.Image:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=q)
    return Image.open(io.BytesIO(buf.getvalue())).convert("RGB")


def _background(w, h, rng):
    base = rng.integers(60, 200, size=3)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    grad = (xx / w * rng.uniform(-40, 40) + yy / h * rng.uniform(-40, 40))[..., None]
    tex = rng.normal(0, 6, size=(h, w, 1))
    arr = np.clip(base[None, None, :] + grad + tex, 0, 255).astype(np.uint8)
    return Image.fromarray(arr).filter(ImageFilter.GaussianBlur(2))


def _perspective_coeffs(src, dst):
    # solve for PIL PERSPECTIVE coefficients mapping dst -> src
    m = []
    for (x, y), (u, v) in zip(dst, src):
        m.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        m.append([0, 0, 0, x, y, 1, -v * x, -v * y])
    A = np.array(m, dtype=np.float64)
    B = np.array(src, dtype=np.float64).reshape(8)
    return np.linalg.solve(A, B).tolist()


def photo(img: Image.Image, steps: list[str], strength: float, rng) -> Image.Image:
    """Apply photo distortions in a fixed, realistic order. strength in [0,1]."""
    im = img.convert("RGB")
    s = strength
    if "moire" in steps:
        a = np.asarray(im).astype(np.float32)
        h, w = a.shape[:2]
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        th = rng.uniform(0.04, 0.12)
        f = rng.uniform(0.9, 1.35)
        g1 = np.sin(2 * np.pi * f * (xx * np.cos(th) + yy * np.sin(th)) / 3.1)
        g2 = np.sin(2 * np.pi * f * (xx * np.cos(-th) + yy * np.sin(-th)) / 3.0)
        pat = (g1 * g2)
        pat = np.asarray(Image.fromarray(((pat + 1) * 127.5).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))).astype(np.float32) / 127.5 - 1
        amp = 10 + 22 * s
        tint = np.array([1.0, 0.85, 1.1])
        a = np.clip(a + pat[..., None] * amp * tint, 0, 255)
        im = Image.fromarray(a.astype(np.uint8))
    if "crop" in steps:
        w, h = im.size
        side = rng.integers(0, 3)
        c = int((0.04 + 0.06 * s) * (w if side == 1 else h))
        if side == 0:      # top cut (status bar half gone)
            im = im.crop((0, c, w, h))
        elif side == 1:    # right edge cut
            im = im.crop((0, 0, w - c, h))
        else:              # bottom cut
            im = im.crop((0, 0, w, h - c))
    if "perspective" in steps or "rotate" in steps or "bezel" in steps:
        # put the screen in a dark bezel and lay it on a surface
        w, h = im.size
        bz = 28
        phone = Image.new("RGB", (w + 2 * bz, h + 2 * bz), (18, 18, 20))
        phone.paste(im, (bz, bz))
        W, H = phone.size
        M = int(0.12 * max(W, H))
        canvas = _background(W + 2 * M, H + 2 * M, rng)
        mask = Image.new("L", phone.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, W - 1, H - 1), radius=70, fill=255)
        canvas.paste(phone, (M, M), mask)
        im = canvas
        if "perspective" in steps:
            CW, CH = im.size
            j = (0.02 + 0.07 * s)
            src = [(M, M), (M + W, M), (M + W, M + H), (M, M + H)]
            dst = []
            for (x, y) in src:
                dst.append((x + rng.uniform(-j, j) * W, y + rng.uniform(-j, j) * H))
            coeffs = _perspective_coeffs(src, dst)
            im = im.transform(im.size, Image.PERSPECTIVE, coeffs, Image.BICUBIC, fillcolor=(40, 40, 40))
        if "rotate" in steps:
            ang = rng.uniform(1.5, 3 + 5 * s) * (1 if rng.random() < 0.5 else -1)
            im = im.rotate(ang, resample=Image.BICUBIC, expand=False, fillcolor=(45, 45, 48))
        # trim most of the surface so the screen fills the frame like a real photo
        CW, CH = im.size
        t = int(M * 0.6)
        im = im.crop((t, t, CW - t, CH - t))
    if "dim" in steps:
        a = np.asarray(im).astype(np.float32) * (0.82 - 0.2 * s) + 6
        im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    if "glare" in steps:
        a = np.asarray(im).astype(np.float32)
        h, w = a.shape[:2]
        cx, cy = rng.uniform(0.2, 0.8) * w, rng.uniform(0.15, 0.7) * h
        r = (0.18 + 0.2 * s) * w
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        d = np.exp(-(((xx - cx) ** 2) / (r * r * 1.8) + ((yy - cy) ** 2) / (r * r * 0.7)))
        a = a + d[..., None] * (70 + 90 * s)
        im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    if "blur" in steps:
        im = im.filter(ImageFilter.GaussianBlur(0.8 + 1.6 * s))
    if "motion_blur" in steps:
        # hand shake: average of copies shifted along a slanted line
        k = int(3 + 6 * s)
        a = np.asarray(im).astype(np.float32)
        acc = np.zeros_like(a)
        for i in range(k):
            acc += np.roll(a, (i // 3, i - k // 2), axis=(0, 1))
        im = Image.fromarray(np.clip(acc / k, 0, 255).astype(np.uint8))
    if "noise" in steps:
        a = np.asarray(im).astype(np.float32)
        a = a + rng.normal(0, 4 + 10 * s, size=a.shape)
        im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    if "downscale" in steps:
        w, h = im.size
        f = 0.78 - 0.25 * s
        im = im.resize((int(w * f), int(h * f)), Image.BILINEAR)
    if "jpeg" in steps:
        im = _jpeg(im, int(70 - 45 * s))
    return im


def contact_sheet(items, out_path, cols=4, thumb_w=260):
    """items: list of (image_path, label_lines). Writes a JPEG contact sheet."""
    from PIL import ImageFont
    font = None
    for p in ["/System/Library/Fonts/AppleSDGothicNeo.ttc", "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"]:
        try:
            font = ImageFont.truetype(p, 15)
            break
        except OSError:
            continue
    font = font or ImageFont.load_default()
    thumbs = []
    for path, lines in items:
        im = Image.open(path).convert("RGB")
        im = ImageOps.contain(im, (thumb_w, int(thumb_w * 2.3)))
        thumbs.append((im, lines))
    th = max(t[0].height for t in thumbs)
    cell_h = th + 70
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (thumb_w + 16) + 16, rows * cell_h + 16), (235, 235, 235))
    d = ImageDraw.Draw(sheet)
    for i, (im, lines) in enumerate(thumbs):
        x = 16 + (i % cols) * (thumb_w + 16)
        y = 16 + (i // cols) * cell_h
        sheet.paste(im, (x, y))
        for k, ln in enumerate(lines):
            d.text((x, y + th + 4 + 18 * k), ln, fill=(20, 20, 20), font=font)
    sheet.save(out_path, "JPEG", quality=82)
