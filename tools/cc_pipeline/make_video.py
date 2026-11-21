"""Original GTA 6 explainer Shorts: 100% original visuals, voice (Windows TTS), music and SFX.

usage: python make_video.py 04 [05 ...]

No game footage, no third-party video, images or music. Everything on screen is drawn here
with Pillow; music is synthesized with numpy; SFX come from channel_branding/sfx (original).
"""
import json, math, os, random, re, subprocess, sys, wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
OUT = Path("D:/GTA6_SHORTS")
BRAND = OUT / "channel_branding"
FONTS = Path("D:/Git/supoclip/backend/fonts")
CH = json.loads(Path("D:/Git/supoclip/shorts_studio/config/channel.json").read_text(encoding="utf-8"))
GROUP_DIR = {"A": "GROUP_A_REFERENCE_INSPIRED", "B": "GROUP_B_FACTS_GLITCHES"}
W, H, FPS = 1080, 1920, 30
GAP = 1.0        # pause after each scene's narration
LEAD = 0.5       # silence before first line
VOICE = "Microsoft Zira Desktop"


def rgb(h):
    h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


PRI, SEC, ACC, DARK, LIGHT = (rgb(CH["colors"][k]) for k in ("primary", "secondary", "accent", "dark", "light"))
DISPLAY = str(FONTS / "Anton-Regular.ttf")
BODY = str(FONTS / "Poppins-ExtraBold.ttf")
_fc = {}


def font(path, size):
    k = (path, size)
    if k not in _fc:
        _fc[k] = ImageFont.truetype(path, size)
    return _fc[k]


# ---------------------------------------------------------------- text helpers
def segs(text):
    """'A [B] C' -> [(A,False),(B,True),(C,False)]"""
    out, buf, hi = [], "", False
    for ch in text:
        if ch in "[]":
            if buf: out.append((buf, hi))
            buf, hi = "", ch == "["
        else:
            buf += ch
    if buf: out.append((buf, hi))
    return out


def wrap_rich(text, f, maxw):
    """tokens = words; a word may contain several highlight pieces (e.g. '[WORTH IT]?')."""
    words, glue = [], False
    for sg, hi in segs(text):
        parts = re.split(r"(\s+)", sg)
        for prt in parts:
            if not prt: continue
            if prt.isspace():
                glue = False; continue
            if glue and words:
                words[-1].append((prt, hi))
            else:
                words.append([(prt, hi)])
            glue = True
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    wt = lambda w: "".join(x for x, _ in w)
    lines, cur = [], []
    for w in words:
        test = cur + [w]
        if cur and d.textlength(" ".join(wt(x) for x in test), font=f) > maxw:
            lines.append(cur); cur = [w]
        else:
            cur = test
    if cur: lines.append(cur)
    return lines


def rich_block(text, path, size, maxw, color=LIGHT, hi=ACC, stroke=8, align="center", line_gap=1.05):
    f = font(path, size)
    while True:
        lines = wrap_rich(text, f, maxw)
        if len(lines) <= 3 or size < 60: break
        size -= 8; f = font(path, size)
    d0 = ImageDraw.Draw(Image.new("L", (1, 1)))
    lh = int(size * line_gap) + stroke
    hgt = lh * len(lines) + stroke * 2
    img = Image.new("RGBA", (maxw + stroke * 4, hgt + 10), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    y = stroke
    for ln in lines:
        txt = " ".join("".join(p for p, _ in w) for w in ln)
        tw = d0.textlength(txt, font=f)
        x = (img.width - tw) / 2 if align == "center" else stroke * 2
        for i, w in enumerate(ln):
            for j, (piece, h_) in enumerate(w):
                if j == len(w) - 1 and i < len(ln) - 1: piece += " "
                d.text((x, y), piece, font=f, fill=hi if h_ else color, stroke_width=stroke, stroke_fill=DARK)
                x += d0.textlength(piece, font=f)
        y += lh
    return img.crop(img.getbbox() or (0, 0, 1, 1))


def plain(text, path, size, color=LIGHT, stroke=0, maxw=980):
    return rich_block(text, path, size, maxw, color=color, stroke=stroke)


def pill(text, bg, fg=DARK, size=40, pad=(28, 14)):
    f = font(BODY, size)
    d0 = ImageDraw.Draw(Image.new("L", (1, 1)))
    l, t, r, b = d0.textbbox((0, 0), text, font=f)
    img = Image.new("RGBA", (r - l + pad[0] * 2, b - t + pad[1] * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, img.width - 1, img.height - 1], radius=img.height // 2, fill=bg + (255,))
    d.text((pad[0] - l, pad[1] - t), text, font=f, fill=fg)
    return img


def vstack(parts, gap=30):
    parts = [p for p in parts if p is not None]
    w = max(p.width for p in parts); h = sum(p.height for p in parts) + gap * (len(parts) - 1)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0)); y = 0
    for p in parts:
        img.alpha_composite(p, ((w - p.width) // 2, y)); y += p.height + gap
    return img


# ---------------------------------------------------------------- background
def make_background(seed):
    rnd = random.Random(seed)
    top = np.array([12, 10, 30]); mid = np.array([70, 18, 80]); low = np.array([255, 70, 110])
    ys = np.linspace(0, 1, H)[:, None]
    g = np.where(ys < 0.55, top + (mid - top) * (ys / 0.55), mid + (low - mid) * ((ys - 0.55) / 0.45) ** 1.6)
    arr = np.repeat(g[:, None, :], W, axis=1).reshape(H, W, 3)
    bg = Image.fromarray(arr.clip(0, 255).astype(np.uint8)).convert("RGBA")
    d = ImageDraw.Draw(bg)
    for _ in range(140):  # stars
        x, y = rnd.randrange(W), rnd.randrange(int(H * 0.5)); a = rnd.randrange(60, 200)
        d.ellipse([x, y, x + 2, y + 2], fill=(255, 255, 255, a))
    # sun with stripes
    cx, cy, r = W // 2, 1380, 300
    sun = Image.new("RGBA", (r * 2, r * 2), (0, 0, 0, 0)); sd = ImageDraw.Draw(sun)
    for i in range(r * 2):
        t = i / (r * 2); col = (int(255), int(214 - 140 * t), int(10 + 90 * t), 255)
        sd.line([(0, i), (r * 2, i)], fill=col)
    mask = Image.new("L", (r * 2, r * 2), 0); md = ImageDraw.Draw(mask); md.ellipse([0, 0, r * 2 - 1, r * 2 - 1], fill=255)
    for k in range(7):
        yy = int(r * 1.0 + k * k * 6 + k * 18); md.rectangle([0, yy, r * 2, yy + 6 + k * 2], fill=0)
    sun.putalpha(mask)
    glow = Image.new("RGBA", bg.size, (0, 0, 0, 0)); gd = ImageDraw.Draw(glow)
    gd.ellipse([cx - r - 80, cy - r - 80, cx + r + 80, cy + r + 80], fill=PRI + (90,))
    bg.alpha_composite(glow.filter(ImageFilter.GaussianBlur(70)))
    bg.alpha_composite(sun, (cx - r, cy - r))
    # horizon / ground
    d.rectangle([0, 1520, W, H], fill=(14, 6, 28, 255))
    # palm silhouettes
    for side in (-1, 1):
        base_x = 90 if side < 0 else W - 90
        pts = []
        for i in range(30):
            t = i / 29; pts.append((base_x + side * -60 * t * t, 1560 - 560 * t))
        for i in range(len(pts) - 1):
            d.line([pts[i], pts[i + 1]], fill=(10, 4, 20, 255), width=int(26 - 14 * i / 30))
        tx, ty = pts[-1]
        for ang in range(0, 360, 40):
            a = math.radians(ang + rnd.randrange(-10, 10)); L = rnd.randrange(170, 240)
            p2 = (tx + math.cos(a) * L, ty + math.sin(a) * L * 0.55 + 40)
            mid_ = ((tx + p2[0]) / 2, (ty + p2[1]) / 2 - 40)
            d.line([(tx, ty), mid_, p2], fill=(10, 4, 20, 255), width=18, joint="curve")
    # dark scrim behind content area for legibility
    scrim = Image.new("RGBA", bg.size, (0, 0, 0, 0)); scd = ImageDraw.Draw(scrim)
    scd.rounded_rectangle([40, 360, W - 40, 1330], radius=48, fill=(8, 6, 20, 150))
    bg.alpha_composite(scrim)
    return bg


def draw_grid(img, t):
    d = ImageDraw.Draw(img)
    hy = 1520
    for i in range(-14, 15):  # converging lines
        d.line([(W / 2 + i * 22, hy), (W / 2 + i * 260, H)], fill=SEC + (150,), width=2)
    off = (t * 0.8) % 1.0
    for k in range(14):  # scrolling horizontal lines
        z = (k + off) / 14
        y = hy + (H - hy) * z ** 2.2
        d.line([(0, y), (W, y)], fill=SEC + (int(60 + 140 * z),), width=2)


# ---------------------------------------------------------------- scene builders
def ease(x):
    x = min(1.0, max(0.0, x)); return 1 - (1 - x) ** 3


def pop(img, t, t0=0.0, dur=0.28):
    """scale-in factor for element appearing at t0"""
    k = ease((t - t0) / dur)
    if k <= 0: return None, 0
    if k >= 1: return img, 1
    s = 0.7 + 0.3 * k
    return img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))), Image.BILINEAR), k


def build_scene(sc, dur):
    """Returns list of layers: dict(img, cx, cy, t0, kind) ; kind: pop|slide|bar"""
    L = []
    typ = sc["type"]
    head = sc.get("head", ""); sub = sc.get("sub", "")
    if typ in ("stat", "year"):
        big = rich_block(sc["value"], DISPLAY, 300 if len(sc["value"]) < 6 else 230, 1000, color=ACC, stroke=12)
        L.append(dict(img=big, cx=W // 2, cy=640, t0=0.05, count=sc["value"] if typ == "stat" else None))
        L.append(dict(img=rich_block(head, DISPLAY, 110, 960), cx=W // 2, cy=880, t0=0.35))
        if sub: L.append(dict(img=plain(sub, BODY, 46, color=LIGHT), cx=W // 2, cy=1030, t0=0.6))
        if typ == "year":
            L.append(dict(img=pill("TIMELINE", SEC), cx=W // 2, cy=440, t0=0.0))
    elif typ in ("text", "end", "duo", "versus"):
        if typ == "duo" or typ == "versus":
            a, b = ("J", "L") if typ == "duo" else ("V", "VI")
            for i, (lab, col) in enumerate(((a, SEC), (b, PRI))):
                c = Image.new("RGBA", (300, 300), (0, 0, 0, 0)); cd = ImageDraw.Draw(c)
                cd.ellipse([0, 0, 299, 299], fill=col + (255,)); cd.ellipse([18, 18, 281, 281], fill=DARK + (255,))
                f = font(DISPLAY, 150 if len(lab) == 1 else 120)
                tw = cd.textlength(lab, font=f); cd.text(((300 - tw) / 2, 50), lab, font=f, fill=col)
                L.append(dict(img=c, cx=W // 2 + (-210 if i == 0 else 210), cy=640, t0=0.1 + 0.2 * i))
            vs = rich_block("VS" if typ == "versus" else "&", DISPLAY, 110, 300, color=ACC)
            L.append(dict(img=vs, cx=W // 2, cy=640, t0=0.5))
            L.append(dict(img=rich_block(head, DISPLAY, 110, 960), cx=W // 2, cy=930, t0=0.3))
            if sub: L.append(dict(img=plain(sub, BODY, 46), cx=W // 2, cy=1070, t0=0.6))
        else:
            L.append(dict(img=rich_block(head, DISPLAY, 140, 960), cx=W // 2, cy=720, t0=0.05))
            if sub: L.append(dict(img=plain(sub, BODY, 50), cx=W // 2, cy=960, t0=0.45))
            if typ == "end":
                L.append(dict(img=pill("FOLLOW FOR MORE", ACC, size=52), cx=W // 2, cy=1130, t0=0.8, pulse=True))
                logo = Image.open(BRAND / "logo_mark.png").convert("RGBA").resize((180, 180))
                L.append(dict(img=logo, cx=W // 2, cy=470, t0=0.2))
    elif typ in ("list", "card"):
        L.append(dict(img=rich_block(head, DISPLAY, 110, 960), cx=W // 2, cy=480, t0=0.0))
        items = sc["items"]; n = len(items)
        for i, it in enumerate(items):
            row = Image.new("RGBA", (940, 130), (0, 0, 0, 0)); rd = ImageDraw.Draw(row)
            rd.rounded_rectangle([0, 0, 939, 129], radius=26, fill=(255, 255, 255, 28), outline=SEC + (200,), width=3)
            rd.rounded_rectangle([0, 0, 18, 129], radius=8, fill=(PRI if i % 2 else ACC) + (255,))
            txt = plain(it, BODY, 48 if len(it) < 30 else 40, maxw=860)
            row.alpha_composite(txt, (50, (130 - txt.height) // 2))
            t0 = 0.5 + i * max(0.6, (dur - 1.5) / max(1, n))
            L.append(dict(img=row, cx=W // 2, cy=650 + i * 160, t0=t0, slide=True))
    elif typ == "bars":
        L.append(dict(img=rich_block(head, DISPLAY, 96, 960), cx=W // 2, cy=470, t0=0.0))
        bars = sc["bars"]; mx = max(v for _, v in bars); mn = sc.get("min", 0); unit = sc.get("unit", "")
        for i, (lab, v) in enumerate(bars):
            frac = (v - mn) / (mx - mn) if mx > mn else 1
            col = PRI if v == mx else (SEC if i % 2 == 0 else ACC)
            valtxt = (f"${v:,.2f}" if unit == "$" else f"{v:g}{unit}" if unit != "B" else f"${v:g}B")
            L.append(dict(img=plain(lab, BODY, 40), cx=W // 2, cy=620 + i * 190, t0=0.3 + i * 0.5, left=80))
            L.append(dict(bar=(80, 660 + i * 190, 920, 70, max(0.04, frac), col), valtxt=valtxt, t0=0.4 + i * 0.5))
    elif typ == "stamp":
        L.append(dict(img=rich_block(head, DISPLAY, 120, 960), cx=W // 2, cy=600, t0=0.0))
        if sub: L.append(dict(img=plain(sub, BODY, 44), cx=W // 2, cy=800, t0=0.3))
        L.append(dict(img=stamp_img(sc["stamp"]), cx=W // 2, cy=1050, t0=0.7, slam=True))
    elif typ in ("rank", "region", "claim"):
        badge = Image.new("RGBA", (230, 230), (0, 0, 0, 0)); bd = ImageDraw.Draw(badge)
        bd.ellipse([0, 0, 229, 229], fill=(PRI if typ != "region" else SEC) + (255,))
        f = font(DISPLAY, 150); tw = bd.textlength(sc["value"], font=f)
        bd.text(((230 - tw) / 2, 18), sc["value"], font=f, fill=LIGHT if typ != "region" else DARK)
        if typ == "rank":
            L.append(dict(img=pill("TRUST RANK", ACC), cx=W // 2, cy=430, t0=0.0))
        L.append(dict(img=badge, cx=W // 2, cy=560, t0=0.05))
        L.append(dict(img=rich_block(head, DISPLAY, 105 if typ != "claim" else 80, 960, color=LIGHT if typ != "claim" else ACC), cx=W // 2, cy=780, t0=0.3))
        if sub: L.append(dict(img=plain(sub, BODY, 44), cx=W // 2, cy=930, t0=0.55))
        if typ == "claim":
            L.append(dict(img=stamp_img(sc["stamp"]), cx=W // 2, cy=1130, t0=min(dur * 0.45, 3.0), slam=True))
    elif typ == "vs":
        L.append(dict(img=rich_block(sc["head"], DISPLAY, 110, 960), cx=W // 2, cy=470, t0=0.0))
        for i, (lab, val, col) in enumerate((("GTA V", sc["left"], SEC), ("GTA VI", sc["right"], PRI))):
            box = Image.new("RGBA", (460, 520), (0, 0, 0, 0)); bd = ImageDraw.Draw(box)
            bd.rounded_rectangle([0, 0, 459, 519], radius=36, fill=(255, 255, 255, 25), outline=col + (255,), width=6)
            tag = pill(lab, col, size=44); box.alpha_composite(tag, ((460 - tag.width) // 2, 30))
            v = rich_block(val, DISPLAY if len(val) < 14 else BODY, 90 if len(val) < 8 else (64 if len(val) < 14 else 46), 400, color=LIGHT, stroke=4)
            box.alpha_composite(v, ((460 - v.width) // 2, 150 + (330 - v.height) // 2))
            L.append(dict(img=box, cx=W // 2 + (-245 if i == 0 else 245), cy=860, t0=0.25 + i * 0.6, slide=True))
    if sc.get("src"):
        L.append(dict(img=pill("SOURCE: " + sc["src"].upper(), (20, 16, 40), fg=SEC, size=28), cx=W // 2, cy=1285, t0=0.6))
    return L


def stamp_img(word):
    col = {"RUMOR": (255, 70, 70), "UNVERIFIED": (255, 140, 40), "ESTIMATE": ACC, "HALF TRUE": ACC, "TRUE": (60, 230, 120),
           "RELEASED": (60, 230, 120), "ALLOWED": (60, 230, 120), "TIED": SEC, "RISKY": (255, 70, 70),
           "UNCONFIRMED": (255, 140, 40)}.get(word, PRI)
    f = font(DISPLAY, 120)
    d0 = ImageDraw.Draw(Image.new("L", (1, 1))); l, t, r, b = d0.textbbox((0, 0), word, font=f)
    img = Image.new("RGBA", (r - l + 80, b - t + 60), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    d.rounded_rectangle([4, 4, img.width - 5, img.height - 5], radius=20, outline=col + (255,), width=12)
    d.text((40 - l, 30 - t), word, font=f, fill=col + (255,))
    return img.rotate(-8, expand=True, resample=Image.BICUBIC)


# ---------------------------------------------------------------- audio
def tts(text, out):
    if out.is_file(): return
    tf = out.with_suffix(".txt"); tf.write_text(text, encoding="utf-8")
    subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(HERE / "tts.ps1"), "-textFile", str(tf),
                    "-outWav", str(out), "-voice", VOICE, "-rate", "0"], check=True)


def wav_read(p):
    with wave.open(str(p)) as w:
        sr = w.getframerate(); x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        if w.getnchannels() == 2: x = x.reshape(-1, 2).mean(1)
    return sr, x


def wav_write(p, x, sr=48000):
    x = np.clip(x, -1, 1)
    with wave.open(str(p), "w") as w:
        w.setnchannels(1 if x.ndim == 1 else 2); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


def synth_music(total, seed, sr=48000):
    """Original synthwave bed: pads + bass + drums. Generated, so no licence needed."""
    rnd = np.random.default_rng(seed)
    bpm = 96 + int(seed % 4) * 4; beat = 60 / bpm
    keys = [57, 55, 53, 52, 50, 59]
    root = keys[seed % len(keys)]
    progs = [[0, -4, 3, -2], [0, 5, -4, 3], [0, -2, -4, -5]]
    prog = progs[seed % 3]
    n = int(total * sr) + sr; t = np.arange(n) / sr
    out = np.zeros(n, np.float32)
    bar = beat * 4
    def hz(m): return 440 * 2 ** ((m - 69) / 12)
    for bi in range(int(total / bar) + 2):
        s0 = int(bi * bar * sr); s1 = min(n, int((bi + 1) * bar * sr))
        if s0 >= n: break
        ch = root + prog[bi % 4]; tt = t[s0:s1] - t[s0]
        env = np.minimum(1, tt / 0.4) * np.minimum(1, (bar - tt) / 0.3)
        pad = sum(np.sin(2 * np.pi * hz(ch + iv) * tt * (1 + det)) for iv in (0, 3 if prog[bi % 4] in (0, -4) else 4, 7, 12) for det in (-0.002, 0.002))
        out[s0:s1] += 0.035 * pad * env
        for q in range(8):  # bass eighths
            b0 = s0 + int(q * beat / 2 * sr); b1 = min(s1, b0 + int(beat / 2 * sr * 0.9))
            if b0 >= s1: break
            bt = t[b0:b1] - t[b0]
            out[b0:b1] += 0.11 * np.sign(np.sin(2 * np.pi * hz(ch - 24) * bt)) * np.exp(-bt * 5) * 0.6
    for k in range(int(total / beat) + 2):  # drums
        b0 = int(k * beat * sr)
        if b0 >= n: break
        L = min(n - b0, int(0.25 * sr)); bt = np.arange(L) / sr
        out[b0:b0 + L] += 0.22 * np.sin(2 * np.pi * (50 + 90 * np.exp(-bt * 30)) * bt) * np.exp(-bt * 12)
        if k % 2 == 1:
            sn = rnd.standard_normal(L) * np.exp(-bt * 18) * 0.06; out[b0:b0 + L] += sn
        h0 = int((k + 0.5) * beat * sr); Lh = min(n - h0, int(0.05 * sr))
        if Lh > 0: out[h0:h0 + Lh] += rnd.standard_normal(Lh) * np.exp(-np.arange(Lh) / sr * 80) * 0.03
    fade = int(1.5 * sr); out[-fade:] *= np.linspace(1, 0, fade); out[:int(0.5 * sr)] *= np.linspace(0, 1, int(0.5 * sr))
    return out[:int(total * sr)]


def words_for(wav_path):
    cache = wav_path.with_suffix(".words.json")
    if cache.is_file(): return json.loads(cache.read_text())
    from faster_whisper import WhisperModel
    m = WhisperModel("base.en", device="cpu", compute_type="int8")
    segs_, _ = m.transcribe(str(wav_path), word_timestamps=True, beam_size=1, vad_filter=False)
    ws = [{"w": w.word.strip(), "s": w.start, "e": w.end} for s in segs_ for w in (s.words or []) if w.word.strip()]
    cache.write_text(json.dumps(ws)); return ws


# ---------------------------------------------------------------- captions
def caption_chunks(words):
    merged = []
    for w in words:  # whisper splits '4,811' into '4' ',811'; glue punctuation-led tokens back on
        if merged and re.match(r"^[,.!?%'’]", w["w"]):
            merged[-1] = {"w": merged[-1]["w"] + w["w"], "s": merged[-1]["s"], "e": w["e"]}
        else:
            merged.append(dict(w))
    words = merged
    chunks, cur = [], []
    for w in words:
        if cur and (len(cur) >= 3 or len(" ".join(x["w"] for x in cur + [w])) > 20 or w["s"] - cur[-1]["e"] > 0.5):
            chunks.append(cur); cur = []
        cur.append(w)
    if cur: chunks.append(cur)
    return chunks


_capc = {}


def caption_img(chunk, active):
    key = (tuple(x["w"] for x in chunk), active)
    if key in _capc: return _capc[key]
    txt = " ".join(("[" + re.sub(r"[\[\]]", "", x["w"]).upper() + "]") if i == active else re.sub(r"[\[\]]", "", x["w"]).upper()
                   for i, x in enumerate(chunk))
    img = rich_block(txt, BODY, 78, 1000, color=LIGHT, hi=ACC, stroke=9)
    if len(_capc) > 400: _capc.clear()
    _capc[key] = img; return img


# ---------------------------------------------------------------- main
def make(cid):
    S = json.loads((HERE / "scripts.json").read_text(encoding="utf-8"))[cid]
    work = HERE / "build" / cid; work.mkdir(parents=True, exist_ok=True)
    cdir = OUT / GROUP_DIR[S["group"]] / f"{cid}_clip"; cdir.mkdir(parents=True, exist_ok=True)
    seed = int(cid)

    # 1. voice per scene
    starts, t = [], LEAD; voice_parts = []
    for i, sc in enumerate(S["scenes"]):
        wp = work / f"vo_{i:02d}.wav"; tts(sc["say"], wp)
        sr, x = wav_read(wp)
        if sr != 48000:
            raise SystemExit("unexpected tts sample rate")
        sc["_start"] = t; sc["_dur"] = len(x) / sr + GAP
        voice_parts.append((t, x)); t += sc["_dur"]
    total = t + 0.6
    voice = np.zeros(int(total * 48000) + 10, np.float32)
    for st, x in voice_parts:
        i0 = int(st * 48000); voice[i0:i0 + len(x)] += x
    wav_write(work / "voice.wav", voice)
    words = words_for(work / "voice.wav")
    chunks = caption_chunks(words)

    # 2. music + sfx mix (python), loudness via ffmpeg later
    music = synth_music(total, seed)
    sfx = {n: wav_read(BRAND / "sfx" / f"{n}.wav")[1] for n in ("whoosh", "pop", "hit", "riser", "ding", "tick")}
    fx = np.zeros_like(voice)
    def put(name, at, g):
        x = sfx[name]; i0 = int(at * 48000); seg = fx[i0:i0 + len(x)]; seg += x[:len(seg)] * g
    for i, sc in enumerate(S["scenes"]):
        if i: put("whoosh", sc["_start"] - 0.15, 0.35)
        if sc["type"] in ("stamp", "claim"): put("hit", sc["_start"] + (0.7 if sc["type"] == "stamp" else min(sc["_dur"] * 0.45, 3.0)), 0.6)
        if sc["type"] in ("stat", "year", "rank", "region"): put("pop", sc["_start"] + 0.05, 0.4)
        if sc["type"] == "end": put("ding", sc["_start"] + 0.8, 0.4)
    # duck music under voice
    env = np.convolve(np.abs(voice[: len(music)]), np.ones(4800) / 4800, mode="same")
    duck = 1 - 0.55 * np.clip(env / (env.max() * 0.25 + 1e-6), 0, 1)
    mix = voice[: len(music)] * 1.0 + music * duck * 0.9 + fx[: len(music)]
    wav_write(work / "mix.wav", mix)

    # 3. frames
    bg = make_background(seed)
    wm = Image.open(BRAND / "watermark.png").convert("RGBA")
    wm.putalpha(wm.getchannel("A").point(lambda a: int(a * CH["watermark"]["opacity"])))
    layers = [build_scene(sc, sc["_dur"]) for sc in S["scenes"]]
    hook = rich_block(S["hook"], DISPLAY, 120, 1000, color=LIGHT, stroke=10)
    tmp = cdir / "final.tmp.mp4"
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                            "-i", "-", "-i", str(work / "mix.wav"),
                            "-af", "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000",
                            "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-threads", "4",
                            "-g", str(FPS * 2), "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest",
                            "-movflags", "+faststart", str(tmp)], stdin=subprocess.PIPE)
    nframes = int(total * FPS)
    si = 0; ci = 0
    for fi in range(nframes):
        tm = fi / FPS
        while si + 1 < len(S["scenes"]) and tm >= S["scenes"][si + 1]["_start"]: si += 1
        sc = S["scenes"][si]; lt = tm - sc["_start"]
        frame = bg.copy(); draw_grid(frame, tm)
        # scene transition flash
        if lt < 0.12 and si > 0:
            frame.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(120 * (1 - lt / 0.12)))))
        d = ImageDraw.Draw(frame)
        for Ly in layers[si]:
            if "bar" in Ly:
                x0, y0, bw, bh, frac, col = Ly["bar"]; k = ease((lt - Ly["t0"]) / 0.8)
                if k <= 0: continue
                d.rounded_rectangle([x0, y0, x0 + bw, y0 + bh], radius=16, fill=(255, 255, 255, 30))
                d.rounded_rectangle([x0, y0, x0 + max(bh, int(bw * frac * k)), y0 + bh], radius=16, fill=col + (255,))
                vt = plain(Ly["valtxt"], DISPLAY, 56, color=DARK if col == ACC else LIGHT) if k >= 1 else None
                if vt is not None and "_vt" not in Ly: Ly["_vt"] = vt
                if k >= 1: frame.alpha_composite(Ly["_vt"], (x0 + 24, y0 + (bh - Ly["_vt"].height) // 2))
                continue
            img = Ly["img"]
            if Ly.get("count") and lt < 0.9:
                m_ = re.match(r"^([^\d]*)([\d,\.]+)(.*)$", Ly["count"])
                if m_:
                    num = float(m_.group(2).replace(",", "")); k = ease(lt / 0.9); dec = len(m_.group(2).split(".")[1]) if "." in m_.group(2) else 0
                    val = num * k; s_ = f"{val:,.{dec}f}" if "," in m_.group(2) or dec else f"{int(val)}"
                    img = rich_block(m_.group(1) + s_ + m_.group(3), DISPLAY, 300 if len(Ly["count"]) < 6 else 230, 1000, color=ACC, stroke=12)
            if Ly.get("slam"):
                k = ease((lt - Ly["t0"]) / 0.18)
                if k <= 0: continue
                s = 1.8 - 0.8 * k; im = img.resize((int(img.width * s), int(img.height * s)), Image.BILINEAR)
                frame.alpha_composite(im, (Ly["cx"] - im.width // 2, Ly["cy"] - im.height // 2)); continue
            if Ly.get("slide"):
                k = ease((lt - Ly["t0"]) / 0.35)
                if k <= 0: continue
                x = Ly["cx"] - img.width // 2 + int((1 - k) * 300)
                frame.alpha_composite(img, (x, Ly["cy"] - img.height // 2)); continue
            im, k = pop(img, lt, Ly["t0"])
            if im is None: continue
            if Ly.get("pulse") and k >= 1:
                s = 1 + 0.05 * math.sin(lt * 6); im = img.resize((int(img.width * s), int(img.height * s)), Image.BILINEAR)
            x = Ly.get("left", Ly["cx"] - im.width // 2)
            frame.alpha_composite(im, (x, Ly["cy"] - im.height // 2))
        # hook banner in first 2.6 s
        if tm < 2.6:
            im, _ = pop(hook, tm, 0.0, 0.2)
            if im is not None:
                d.rectangle([0, 250, W, 250 + hook.height + 40], fill=PRI + (235,))
                frame.alpha_composite(im, ((W - im.width) // 2, 270))
        # captions
        while ci + 1 < len(chunks) and tm >= chunks[ci + 1][0]["s"]: ci += 1
        ch = chunks[ci] if chunks else None
        if ch and ch[0]["s"] <= tm <= ch[-1]["e"] + 0.35:
            act = max(i for i, w in enumerate(ch) if w["s"] <= tm or i == 0)
            cimg = caption_img(ch, act)
            frame.alpha_composite(cimg, ((W - cimg.width) // 2, 1440))
        # watermark + progress bar
        frame.alpha_composite(wm, (CH["watermark"]["margin_x"], CH["watermark"]["margin_y"]))
        d.rectangle([0, H - 14, int(W * tm / total), H], fill=ACC + (255,))
        enc.stdin.write(frame.convert("RGB").tobytes())
    enc.stdin.close(); enc.wait()
    if enc.returncode: raise SystemExit(f"encode failed {cid}")
    os.replace(tmp, cdir / "final.mp4")

    # 4. thumbnail
    th = make_background(seed + 100)
    th.alpha_composite(rich_block(S["thumb"], DISPLAY, 210, 1000, stroke=14), (0, 0)) if False else None
    big = rich_block(S["thumb"].replace("|", " "), DISPLAY, 210, 1000, stroke=14)
    th.alpha_composite(big, ((W - big.width) // 2, 760 - big.height // 2))
    th.alpha_composite(Image.open(BRAND / "logo_wordmark.png").convert("RGBA").resize((520, 128)), ((W - 520) // 2, 1180))
    th.convert("RGB").save(cdir / "thumbnail.jpg", quality=92)
    json.dump({"duration": total, "scenes": [{k: v for k, v in s.items() if not k.startswith("_") or k in ("_start", "_dur")} for s in S["scenes"]],
               "caption_words": len(words)}, open(cdir / "render_log.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"{cid}: {total:.1f}s -> {cdir / 'final.mp4'}", flush=True)


if __name__ == "__main__":
    for c in sys.argv[1:]:
        make(c)
