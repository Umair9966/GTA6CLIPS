"""Original channel branding, drawn from scratch with Pillow.

Everything here is generated geometry plus OFL-licensed Google Fonts shipped in
SupoClip's backend/fonts. No Rockstar / GTA marks, no other creator's branding.
Change config/channel.json and re-run `python -m studio brand` to rebrand.
"""
from __future__ import annotations

import math
import shutil
import tempfile
from pathlib import Path
from typing import Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .common import FONTS_DIR, H, W, X264_LOW_MEM, branding_dir, channel, font_path, hex_rgb, project, run

SS = 4  # supersampling factor for anti-aliased geometry


def _lerp(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def draw_mark(px: int) -> Image.Image:
    """The logo mark: a gradient 'replay' loop with an arrowhead around a play triangle."""
    cfg = channel()["colors"]
    p, s, light = hex_rgb(cfg["primary"]), hex_rgb(cfg["secondary"]), hex_rgb(cfg["light"])
    size = px * SS
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = size / 2
    r = size * 0.38
    th = int(size * 0.11)
    start, end, steps = -20.0, 235.0, 90
    for i in range(steps):
        a0 = start + (end - start) * i / steps
        a1 = start + (end - start) * (i + 1) / steps + 0.6
        d.arc([c - r, c - r, c + r, c + r], a0, a1, fill=_lerp(p, s, i / steps) + (255,), width=th)
    # Arrowhead continuing clockwise travel at the `end` angle.
    theta = math.radians(end)
    px_, py_ = c + (r - th / 2) * math.cos(theta), c + (r - th / 2) * math.sin(theta)
    tx, ty = -math.sin(theta), math.cos(theta)
    nx, ny = math.cos(theta), math.sin(theta)
    head = th * 1.25
    tip = (px_ + tx * head * 1.3, py_ + ty * head * 1.3)
    b1 = (px_ + nx * head, py_ + ny * head)
    b2 = (px_ - nx * head, py_ - ny * head)
    d.polygon([tip, b1, b2], fill=s + (255,))
    # Play triangle.
    t = size * 0.15
    d.polygon([(c - t * 0.8, c - t), (c - t * 0.8, c + t), (c + t * 1.05, c)], fill=light + (255,))
    return img.resize((px, px), Image.LANCZOS)


def _font(key: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(font_path(key)), size)


def _name_parts() -> Tuple[str, str]:
    words = channel()["channel_name"].split()
    if len(words) == 1:
        return "", words[0]
    return " ".join(words[:-1]) + " ", words[-1]


def draw_wordmark(height: int, with_handle: bool = True) -> Image.Image:
    cfg = channel()
    light, primary = hex_rgb(cfg["colors"]["light"]), hex_rgb(cfg["colors"]["primary"])
    hs = height * SS
    font = _font("display", int(hs * 0.62))
    first, last = _name_parts()
    measure = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    w1 = measure.textlength(first, font=font)
    w2 = measure.textlength(last, font=font)
    gap = hs * 0.18
    width = int(hs + gap + w1 + w2 + hs * 0.1)
    img = Image.new("RGBA", (width, hs), (0, 0, 0, 0))
    img.alpha_composite(draw_mark(height).resize((hs, hs), Image.LANCZOS), (0, 0))
    d = ImageDraw.Draw(img)
    x = hs + gap
    y = hs * 0.47 if with_handle else hs * 0.5
    d.text((x, y), first, font=font, fill=light + (255,), anchor="lm")
    d.text((x + w1, y), last, font=font, fill=primary + (255,), anchor="lm")
    if with_handle:
        hfont = _font("caption", int(hs * 0.16))
        d.text((x + 4, hs * 0.86), cfg["handle"], font=hfont, fill=light + (200,), anchor="lm")
    return img.resize((max(1, width // SS), height), Image.LANCZOS)


def draw_watermark() -> Image.Image:
    """Small pill: mark + channel name, on a translucent dark backing for legibility."""
    cfg = channel()
    h = int(cfg["watermark"]["height"])
    hs = h * SS
    dark, light, primary = (hex_rgb(cfg["colors"][k]) for k in ("dark", "light", "primary"))
    font = _font("display", int(hs * 0.50))
    first, last = _name_parts()
    measure = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    w1, w2 = measure.textlength(first, font=font), measure.textlength(last, font=font)
    pad = hs * 0.16
    mark = int(hs * 0.78)
    width = int(pad + mark + pad * 0.8 + w1 + w2 + pad * 1.6)
    img = Image.new("RGBA", (width, hs), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, width - 1, hs - 1], radius=hs // 2, fill=dark + (165,))
    img.alpha_composite(draw_mark(mark // SS).resize((mark, mark), Image.LANCZOS), (int(pad), (hs - mark) // 2))
    x = pad + mark + pad * 0.8
    d.text((x, hs / 2), first, font=font, fill=light + (255,), anchor="lm")
    d.text((x + w1, hs / 2), last, font=font, fill=primary + (255,), anchor="lm")
    return img.resize((max(1, width // SS), h), Image.LANCZOS)


def _gradient_bg(size, top, bottom) -> Image.Image:
    w, h = size
    col = Image.new("RGB", (1, h))
    for y in range(h):
        col.putpixel((0, y), _lerp(top, bottom, y / max(1, h - 1)))
    return col.resize((w, h)).convert("RGBA")


def draw_avatar(px: int = 800) -> Image.Image:
    cfg = channel()["colors"]
    img = _gradient_bg((px, px), hex_rgb(cfg["dark"]), _lerp(hex_rgb(cfg["dark"]), hex_rgb(cfg["primary"]), 0.25))
    mark = draw_mark(int(px * 0.78))
    img.alpha_composite(mark, ((px - mark.width) // 2, (px - mark.height) // 2))
    return img


def draw_banner() -> Image.Image:
    cfg = channel()
    colors = cfg["colors"]
    img = _gradient_bg((2560, 1440), hex_rgb(colors["dark"]), _lerp(hex_rgb(colors["dark"]), hex_rgb(colors["secondary"]), 0.18))
    d = ImageDraw.Draw(img)
    for i in range(14):  # subtle diagonal speed lines, original decoration
        x = 200 + i * 170
        d.line([(x, 1440), (x + 600, 0)], fill=hex_rgb(colors["primary"]) + (18,), width=6)
    wm = draw_wordmark(230, with_handle=False)
    img.alpha_composite(wm, ((2560 - wm.width) // 2, 720 - 150))
    tfont = _font("caption", 54)
    d.text((1280, 720 + 125), cfg["tagline"], font=tfont, fill=hex_rgb(colors["accent"]) + (255,), anchor="mm")
    return img


def _ease_out_back(t: float) -> float:
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def render_sting(out_path: Path, seconds: float, kind: str) -> None:
    """Outro ('WATCH IT AGAIN' replay prompt) or short intro sting, 1080x1920."""
    cfg = channel()
    colors = cfg["colors"]
    fps = int(project()["fps"])
    frames = int(round(seconds * fps))
    base = _gradient_bg((W, H), hex_rgb(colors["dark"]), _lerp(hex_rgb(colors["dark"]), hex_rgb(colors["primary"]), 0.22))
    mark_full = draw_mark(520)
    wordmark = draw_wordmark(120, with_handle=True)
    cta_font = _font("display", 96)
    tmp = Path(tempfile.mkdtemp(prefix="sting_"))
    try:
        for i in range(frames):
            t = i / max(1, frames - 1)
            frame = base.copy()
            k = _ease_out_back(min(1.0, t / 0.45))
            size = max(2, int(520 * max(0.05, k)))
            mark = mark_full.resize((size, size), Image.LANCZOS).rotate(-90 * (1 - min(1.0, t / 0.45)), resample=Image.BICUBIC)
            frame.alpha_composite(mark, ((W - mark.width) // 2, 640 - mark.height // 2))
            if kind == "outro":
                a = max(0.0, min(1.0, (t - 0.3) / 0.25))
                wm = wordmark.copy()
                wm.putalpha(wm.getchannel("A").point(lambda v: int(v * a)))
                frame.alpha_composite(wm, ((W - wm.width) // 2, int(1010 + 40 * (1 - a))))
                b = max(0.0, min(1.0, (t - 0.5) / 0.2))
                if b > 0:
                    d = ImageDraw.Draw(frame)
                    d.text((W // 2, 1300), "WATCH IT AGAIN", font=cta_font,
                           fill=hex_rgb(colors["accent"]) + (int(255 * b),), anchor="mm",
                           stroke_width=6, stroke_fill=hex_rgb(colors["dark"]) + (int(255 * b),))
            frame.convert("RGB").save(tmp / f"{i:04d}.png")
        run(["ffmpeg", "-y", "-framerate", fps, "-i", tmp / "%04d.png",
             "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", f"{frames / fps:.3f}",
             "-c:v", "libx264", *X264_LOW_MEM, "-crf", "16", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", out_path])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def draw_caption_preview() -> Image.Image:
    cfg = channel()
    colors = cfg["colors"]
    img = _gradient_bg((W, H), (40, 46, 60), (20, 24, 34))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 292, W, 292 + 1216], fill=(70, 80, 100, 255))
    d.text((W // 2, 900), "GAMEPLAY AREA", font=_font("caption", 54), fill=(150, 160, 180, 255), anchor="mm")
    wm = draw_watermark()
    img.alpha_composite(wm, (cfg["watermark"]["margin_x"], cfg["watermark"]["margin_y"]))
    d.text((W // 2, 360), "HOOK TEXT GOES HERE", font=_font("display", 104), fill=hex_rgb(colors["light"]),
           anchor="mm", stroke_width=8, stroke_fill=hex_rgb(colors["dark"]))
    cap_font = _font("caption", 80)
    words = ["THIS", "WAS", "CRAZY"]
    widths = [d.textlength(w + " ", font=cap_font) for w in words]
    x = W / 2 - sum(widths) / 2
    for word, wdt, active in zip(words, widths, [False, True, False]):
        d.text((x, 1330), word, font=cap_font, anchor="lm",
               fill=hex_rgb(colors["accent"] if active else colors["light"]), stroke_width=7, stroke_fill=(0, 0, 0))
        x += wdt
    d.text((W // 2, 1180), "REPLAY x0.5", font=_font("display", 84), fill=hex_rgb(colors["accent"]),
           anchor="mm", stroke_width=6, stroke_fill=hex_rgb(colors["dark"]))
    d.text((W // 2, 1650), "(bottom ~20%: YouTube UI - keep clear)", font=_font("caption", 36),
           fill=(150, 160, 180, 255), anchor="mm")
    return img


def build_brand_guide(out: Path) -> None:
    cfg = channel()
    c = cfg["colors"]
    wm = cfg["watermark"]
    text = f"""# {cfg['channel_name']} - Brand Guide

Generated by `python -m studio brand` from `shorts_studio/config/channel.json`.
Change the name, handle or colours there and re-run to regenerate every asset.

## Identity
- Channel name: **{cfg['channel_name']}** (configurable)
- Handle: {cfg['handle']}
- Tagline: {cfg['tagline']}
- Mark: original gradient "replay loop" with arrowhead around a play triangle. It stands for
  the channel's format of replaying the best moment. It uses no Rockstar or GTA marks, logos,
  fonts or colour trade dress, and does not imitate any creator's branding.

## Colour palette
| Role | Hex | Use |
|---|---|---|
| Primary | {c['primary']} | last word of name, highlight borders, accents |
| Secondary | {c['secondary']} | mark gradient end, fact-video accents |
| Accent | {c['accent']} | active caption word, labels, call to action |
| Dark | {c['dark']} | backgrounds, text outlines |
| Light | {c['light']} | body text, captions |

## Typography (SIL Open Font License 1.1, so commercial use is allowed)
- Display / hooks / labels: **Anton** (`{cfg['fonts']['display']}`)
- Captions: **Poppins ExtraBold** (`{cfg['fonts']['caption']}`)
- Source: Google Fonts, bundled in `supoclip/backend/fonts` (see its SOURCES.md).

## Watermark
- File: `watermark.png` (transparent PNG)
- Position: {wm['position']}, {wm['margin_x']}px from left, {wm['margin_y']}px from top of the 1080x1920 frame
  (above the gameplay panel and below the Shorts top bar, clear of captions and bottom UI)
- Height {wm['height']}px, opacity {wm['opacity']}
- Applied to every frame of every export except the outro sting, which already carries the full logo.

## Layout safe zones (1080x1920)
- 0-150px: Shorts top bar, so no important content
- 170-242px: watermark (left)
- ~300-420px: hook title (first 2-3 s)
- 292-1508px: gameplay panel
- ~1180px: labels (REPLAY, WAIT FOR IT)
- ~1330px: captions
- below ~1500px: Shorts title/channel UI, so nothing important

## Files
- `logo_mark.png` (1024px), `logo_wordmark.png`, `watermark.png`, `avatar_800.png`,
  `banner_2560x1440.png`, `caption_style_preview.png`, `outro_sting.mp4`, `intro_sting.mp4`
- `sfx/` original synthesized sound effects (generated with ffmpeg, no third-party samples)
"""
    out.write_text(text, encoding="utf-8")


def build_all() -> Path:
    out = branding_dir()
    out.mkdir(parents=True, exist_ok=True)
    draw_mark(1024).save(out / "logo_mark.png")
    draw_wordmark(256).save(out / "logo_wordmark.png")
    draw_watermark().save(out / "watermark.png")
    draw_avatar().save(out / "avatar_800.png")
    draw_banner().convert("RGB").save(out / "banner_2560x1440.png")
    draw_caption_preview().convert("RGB").save(out / "caption_style_preview.png")
    render_sting(out / "outro_sting.mp4", 1.2, "outro")
    render_sting(out / "intro_sting.mp4", 0.6, "intro")
    build_brand_guide(out / "brand_guide.md")
    from .sfx import build_sfx
    build_sfx(out / "sfx")
    return out
