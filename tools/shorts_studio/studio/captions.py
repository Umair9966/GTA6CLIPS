"""ASS subtitle builder: word-pop captions, hook titles, shot labels and fact cards.

Caption timing sources, best first:
  1. `words`: word-level timestamps in SOURCE time (e.g. from SupoClip's AssemblyAI/Whisper
     transcript) -> exact sync.
  2. `captions` with `src: [start, end]` in SOURCE time -> mapped through the edit; words are
     spread across the line proportionally to their length.
  3. `captions` with `t0/t1` in OUTPUT time (on-screen text that is not speech).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import ImageFont

from .common import H, W, ass_color, channel, font_path

# Per-clip vertical positions (set by build_ass from the manifest).
POS = {"caption": 1330, "label": 1180, "card": 1180}


def _family(key: str) -> str:
    return ImageFont.truetype(str(font_path(key)), 20).getname()[0]


def ts(sec: float) -> str:
    sec = max(0.0, sec)
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", "\\N")


def header() -> str:
    cfg = channel()
    c = cfg["colors"]
    disp, cap = _family("display"), _family("caption")
    light, dark, accent = ass_color(c["light"]), ass_color(c["dark"]), ass_color(c["accent"])
    card_back = ass_color(c["primary"], 0x18)
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{cap},80,{light},{accent},&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,7,2,5,60,60,0,1
Style: Hook,{disp},108,{light},{accent},{dark},&H64000000,0,0,0,0,100,100,1,0,1,9,3,8,60,60,0,1
Style: Label,{disp},84,{accent},{light},{dark},&H64000000,0,0,0,0,100,100,2,0,1,7,2,5,60,60,0,1
Style: Card,{disp},74,{light},{accent},{card_back},{card_back},0,0,0,0,100,100,1,0,3,22,0,5,90,90,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _highlight(text: str) -> str:
    """[bracketed] words render in the accent colour."""
    accent = ass_color(channel()["colors"]["accent"])
    out, buf, inside = [], "", False
    for ch in text:
        if ch == "[" and not inside:
            out.append(esc(buf)); buf = ""; inside = True
        elif ch == "]" and inside:
            out.append(f"{{\\c{accent}}}{esc(buf)}{{\\r}}"); buf = ""; inside = False
        else:
            buf += ch
    out.append(esc(buf))
    return "".join(out)


def text_event(t0: float, t1: float, style: str, text: str) -> str:
    pos = {"Hook": (540, 300), "Label": (540, POS["label"]), "Card": (540, POS["card"]), "Caption": (540, POS["caption"])}[style]
    anim = "\\fscx70\\fscy70\\t(0,120,\\fscx100\\fscy100)" if style in ("Label", "Hook") else "\\fad(120,120)"
    return f"Dialogue: 2,{ts(t0)},{ts(t1)},{style},,0,0,0,,{{\\pos({pos[0]},{pos[1]}){anim}}}{_highlight(text)}"


def word_events(words: List[Tuple[str, float, float]], chunk: int = 3, max_chars: int = 18) -> List[str]:
    """Group words into short chunks; one event per word with the active word highlighted."""
    accent = ass_color(channel()["colors"]["accent"])
    chunks: List[List[Tuple[str, float, float]]] = []
    cur: List[Tuple[str, float, float]] = []
    for w in words:
        if cur and (len(cur) >= chunk or len(" ".join(x[0] for x in cur + [w])) > max_chars
                    or w[1] - cur[-1][2] > 0.6):
            chunks.append(cur); cur = []
        cur.append(w)
    if cur:
        chunks.append(cur)
    events = []
    for ci, ch in enumerate(chunks):
        chunk_end = ch[-1][2]
        if ci + 1 < len(chunks):
            chunk_end = min(chunk_end + 0.25, chunks[ci + 1][0][1])
        for wi, (word, s, e) in enumerate(ch):
            end = ch[wi + 1][1] if wi + 1 < len(ch) else chunk_end
            if end - s < 0.04:
                continue
            parts = []
            for j, (wj, _, _) in enumerate(ch):
                token = esc(wj.upper())
                parts.append(f"{{\\c{accent}\\fscx112\\fscy112}}{token}{{\\r}}" if j == wi else token)
            pop = "\\fscx85\\fscy85\\t(0,90,\\fscx100\\fscy100)" if wi == 0 else ""
            events.append(f"Dialogue: 1,{ts(s)},{ts(end)},Caption,,0,0,0,,{{\\pos(540,{POS['caption']}){pop}}}{' '.join(parts)}")
    return events


def spread_words(text: str, t0: float, t1: float) -> List[Tuple[str, float, float]]:
    words = text.split()
    if not words:
        return []
    weights = [len(w) + 2 for w in words]
    total = float(sum(weights))
    out, t = [], t0
    for w, wt in zip(words, weights):
        d = (t1 - t0) * wt / total
        out.append((w, t, t + d))
        t += d
    return out


def map_source_time(s: float, e: float, timeline: List[Dict[str, Any]],
                    include_replays: bool = False) -> Optional[Tuple[float, float]]:
    """Map a source interval to output time via the first play shot that contains it."""
    for shot in timeline:
        if shot["type"] == "freeze" or (shot["type"] == "replay" and not include_replays):
            continue
        a, b = shot["in"], shot["out"]
        if e <= a or s >= b:
            continue
        s2, e2 = max(s, a), min(e, b)
        return (shot["start"] + (s2 - a) / shot["speed"], shot["start"] + (e2 - a) / shot["speed"])
    return None


def build_ass(m: Dict[str, Any], timeline: List[Dict[str, Any]], total: float, out_path: Path) -> Dict[str, Any]:
    POS["caption"] = int(m.get("caption_y", 1330))
    POS["label"] = int(m.get("label_y", 1180))
    POS["card"] = int(m.get("card_y", POS["label"]))
    events: List[str] = []
    word_list: List[Tuple[str, float, float]] = []
    sync = "none"

    if m.get("words"):
        sync = "word-level timestamps (source time)"
        for w in m["words"]:
            mapped = map_source_time(w["s"], w["e"], timeline)
            if mapped:
                word_list.append((w["w"], *mapped))
    for cap in m.get("captions", []):
        if "src" in cap:
            sync = "line timestamps (source time), words interpolated" if sync == "none" else sync
            mapped = map_source_time(cap["src"][0], cap["src"][1], timeline, cap.get("in_replay", False))
            if mapped:
                word_list.extend(spread_words(cap["text"], *mapped))
        else:
            sync = "output-time on-screen text" if sync == "none" else sync
            word_list.extend(spread_words(cap["text"], cap["t0"], cap["t1"]))
    word_list.sort(key=lambda x: x[1])
    events.extend(word_events(word_list))

    for item in m.get("texts", []):
        if item["t0"] >= total - 0.1:
            continue
        style = {"hook": "Hook", "label": "Label", "card": "Card", "caption": "Caption"}[item.get("style", "card")]
        events.append(text_event(item["t0"], min(item["t1"], total), style, item["text"]))
    for shot in timeline:
        label = shot.get("label")
        if label is None and shot["type"] == "replay":
            label = f"REPLAY x{shot['speed']:g}" if shot["speed"] != 1 else "REPLAY"
        if label and shot["start"] < total:
            events.append(text_event(shot["start"] + 0.05, shot["start"] + min(shot["dur"], 1.6), "Label", label))

    out_path.write_text(header() + "\n".join(events) + "\n", encoding="utf-8-sig")
    return {"caption_sync": sync, "caption_words": len(word_list), "events": len(events)}
