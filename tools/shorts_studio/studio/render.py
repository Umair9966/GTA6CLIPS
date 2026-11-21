"""Render a clip manifest to a branded 1080x1920 Short.

Pipeline per clip:
  1. rights gate (rights.py): BLOCKED clips never render
  2. each shot -> uniform 1080x1920 intermediate (framing, zoom ramp, freeze, replay, fx)
  3. one assembly pass: cuts/xfades, ASS captions, watermark, SFX, loudness normalisation, outro sting
  4. thumbnail.jpg from the final render

Source footage is only ever read. Outputs go to the clip folder, written to a temp
name first and then moved into place.
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from . import rights
from .captions import build_ass
from .common import (H, W, X264_LOW_MEM, branding_dir, channel, clip_dir, even, font_path, hex_rgb,
                     media_info, project, run, save_json)

XFADE_DUR = 0.2
FG_ASPECT = 8 / 9  # gameplay panel aspect in "blur" framing (1080x1216)


def _atempo(speed: float) -> str:
    if abs(speed - 1.0) < 1e-6:
        return ""
    parts, s = [], speed
    while s < 0.5:
        parts.append("atempo=0.5"); s /= 0.5
    while s > 2.0:
        parts.append("atempo=2.0"); s /= 2.0
    parts.append(f"atempo={s:.4f}")
    return ",".join(parts) + ","


_INFO_CACHE: Dict[str, Dict[str, Any]] = {}


def shot_source(s: Dict[str, Any], default_src: Path, default_info: Dict[str, Any]):
    """A shot may take its footage from another file via "src" (multi-source compilations)."""
    if not s.get("src"):
        return default_src, default_info
    p = Path(s["src"]).resolve()
    if str(p) not in _INFO_CACHE:
        _INFO_CACHE[str(p)] = media_info(p)
    return p, _INFO_CACHE[str(p)]


def normalize_shots(m: Dict[str, Any], info: Dict[str, Any], src: Optional[Path] = None) -> List[Dict[str, Any]]:
    shots = []
    for raw in m.get("shots", []):
        src_dur = shot_source(raw, src, info)[1]["duration"]
        s = dict(raw)
        t = s.get("type", "play")
        s["type"] = t
        if t == "freeze":
            s["in"] = s["out"] = float(s["at"])
            s["speed"] = 1.0
            s["dur"] = float(s.get("dur", 0.8))
            s.setdefault("zoom", [1.12, 1.3])
            s.setdefault("fx", ["flash"])
            s.setdefault("audio", "mute")
        else:
            s["in"], s["out"] = float(s["in"]), float(s["out"])
            s["speed"] = float(s.get("speed", 0.5 if t == "replay" else 1.0))
            s["dur"] = (s["out"] - s["in"]) / s["speed"]
            if t == "replay":
                s.setdefault("fx", ["highlight", "flash"])
        if s["in"] < 0 or s["out"] > src_dur + 0.05 or s["dur"] <= 0:
            raise ValueError(f"Shot {raw} is outside the source (duration {src_dur:.2f}s)")
        shots.append(s)
    if not shots:
        raise ValueError("Manifest has no shots")
    return shots


def _render_shot(src: Path, info: Dict[str, Any], m: Dict[str, Any], s: Dict[str, Any], out: Path) -> None:
    fps = int(project()["fps"])
    primary = channel()["colors"]["primary"].lstrip("#")
    dur = s["dur"]
    sw, sh = info["width"], info["height"]
    framing = s.get("framing", m.get("framing", "blur"))
    fx_, fy_ = s.get("focus", m.get("focus", [0.5, 0.5]))
    zs, ze = [float(z) for z in s.get("zoom", [1.0, 1.0])]

    if s["type"] == "freeze":
        in_args = ["-ss", f"{s['in']:.3f}", "-t", "0.5", "-i", src]
        v0 = f"[0:v]trim=end_frame=1,setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration={dur + 0.2:.3f},fps={fps}"
    else:
        in_args = ["-ss", f"{s['in']:.3f}", "-t", f"{s['out'] - s['in']:.3f}", "-i", src]
        v0 = f"[0:v]setpts=(PTS-STARTPTS)/{s['speed']},fps={fps}"
    v0 += ",format=yuv420p"

    cam_h = 0
    if framing == "stream":
        # Streamer layout: facecam panel on top, gameplay panel below (no blurred background).
        cam_h = int(m.get("cam_panel_h", 676))
        box_w, box_h, need_bg = W, H - cam_h, False
    elif framing in ("fill", "native"):
        box_w, box_h, need_bg = W, H, False
    elif framing == "fit":
        box_w, box_h, need_bg = W, even(W * sh / sw), True
    else:
        box_w, box_h, need_bg = W, even(W / FG_ASPECT), True
    fg_y = max(0, (H - box_h) // 2 - 60) if need_bg else cam_h

    target = box_w / box_h
    if sw / sh > target:
        cw, ch = even(sh * target), sh
    else:
        cw, ch = sw, even(sw / target)
    cx, cy = int((sw - cw) * fx_), int((sh - ch) * fy_)
    fg = f"crop={cw}:{ch}:{cx}:{cy}"
    if abs(zs - 1) < 1e-6 and abs(ze - 1) < 1e-6:
        fg += f",scale={box_w}:{box_h}:flags=lanczos"
    elif abs(zs - ze) < 1e-6:
        zw, zh = even(cw / zs), even(ch / zs)
        fg += f",crop={zw}:{zh}:{int((cw - zw) * fx_)}:{int((ch - zh) * fy_)},scale={box_w}:{box_h}:flags=lanczos"
    else:
        fg += (f",scale={box_w * 2}:{box_h * 2}:flags=lanczos,"
               f"zoompan=z='{zs}+({ze}-{zs})*min(1,it/{dur:.3f})':x='(iw-iw/zoom)*{fx_}':y='(ih-ih/zoom)*{fy_}'"
               f":d=1:s={box_w}x{box_h}:fps={fps}")
    fg += ",unsharp=5:5:0.5"

    if framing == "stream":
        # cam box in source pixels, normalised [x, y, w, h]
        nx, ny, nw, nh = s.get("cam", m.get("cam", [0.0, 0.426, 0.202, 0.225]))
        kw, kh = even(nw * sw), even(nh * sh)
        kx, ky = int(nx * sw), int(ny * sh)
        graph = (f"{v0},split=2[a][b];"
                 f"[a]crop={kw}:{kh}:{kx}:{ky},scale={W}:{cam_h}:force_original_aspect_ratio=increase:flags=lanczos,"
                 f"crop={W}:{cam_h},unsharp=5:5:0.6[cam];"
                 f"[b]{fg}[fg];[cam][fg]vstack=inputs=2,"
                 f"drawbox=x=0:y={cam_h - 3}:w={W}:h=6:color=0x{primary}@1:t=fill[c]")
    elif need_bg:
        graph = (f"{v0},split=2[a][b];"
                 f"[a]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,gblur=sigma=10,"
                 f"scale={W}:{H},eq=brightness=-0.10:saturation=1.25[bg];"
                 f"[b]{fg}[fg];[bg][fg]overlay=0:{fg_y}:shortest=1[c]")
    else:
        graph = f"{v0},{fg}[c]"

    post = []
    for fx in s.get("fx", []):
        if fx == "highlight":
            post += [f"drawbox=x=0:y={fg_y}:w={W}:h={box_h}:color=0x{primary}@0.95:t=10", "eq=saturation=1.2:contrast=1.06"]
        elif fx == "bw":
            post.append("hue=s=0")
        elif fx == "vignette":
            post.append("vignette=PI/5")
        elif fx == "shake":
            post.append(f"scale=1134:2016,crop={W}:{H}:x='27+18*sin(t*50)':y='48+18*cos(t*43)'")
        elif fx == "glitch":
            post.append("rgbashift=rh=-14:bh=14:enable='lt(mod(t,0.5),0.12)'")
        elif fx == "flash":
            post.append("fade=t=in:st=0:d=0.15:color=white")
    post += ["setsar=1", "format=yuv420p", f"trim=duration={dur:.3f}"]
    graph += f";[c]{','.join(post)}[v]"

    audio_mode = s.get("audio", "keep")
    if info["has_audio"] and s["type"] != "freeze" and audio_mode != "mute":
        vol = 0.35 if audio_mode == "duck" else 1.0
        graph += (f";[0:a]asetpts=PTS-STARTPTS,{_atempo(s['speed'])}aresample=48000,"
                  f"aformat=sample_fmts=fltp:channel_layouts=stereo,volume={vol},apad,atrim=duration={dur:.3f}[a]")
        extra = []
    else:
        graph += f";[1:a]atrim=duration={dur:.3f}[a]"
        extra = ["-f", "lavfi", "-t", f"{dur + 0.5:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]

    gfile = out.with_suffix(".graph.txt")
    gfile.write_text(graph, encoding="utf-8")
    run(["ffmpeg", "-y", *in_args, *extra, "-/filter_complex", gfile, "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", *X264_LOW_MEM, "-preset", "veryfast", "-crf", "16", "-r", fps,
         "-c:a", "pcm_s16le", "-ar", "48000", "-t", f"{dur:.3f}", out])


def _auto_sfx(m: Dict[str, Any], timeline: List[Dict[str, Any]], outro_start: Optional[float]) -> List[Dict[str, Any]]:
    events = list(m.get("sfx", []))
    if m.get("auto_sfx", True):
        for i, s in enumerate(timeline):
            if i > 0:
                events.append({"t": max(0.0, s["start"] - 0.2), "name": "whoosh", "gain": 0.55})
            if s["type"] == "freeze":
                events.append({"t": s["start"], "name": "hit", "gain": 0.9})
            elif s["type"] == "replay":
                events.append({"t": s["start"], "name": "rewind", "gain": 0.6})
        if outro_start is not None:
            events += [{"t": outro_start + 0.05, "name": "pop", "gain": 0.8},
                       {"t": outro_start + 0.6, "name": "ding", "gain": 0.5}]
    events.sort(key=lambda e: e["t"])
    dedup: List[Dict[str, Any]] = []
    for e in events:
        if dedup and e["name"] == dedup[-1]["name"] and abs(e["t"] - dedup[-1]["t"]) < 0.15:
            continue
        dedup.append(e)
    return dedup


def make_thumbnail(final: Path, m: Dict[str, Any], out: Path, duration: float) -> None:
    cfg = channel()
    th = m.get("thumbnail", {})
    t = float(th.get("time", duration * 0.4))
    frame = out.with_suffix(".frame.png")
    run(["ffmpeg", "-y", "-ss", f"{min(t, duration - 0.1):.3f}", "-i", final, "-frames:v", "1", frame])
    img = Image.open(frame).convert("RGBA")
    frame.unlink(missing_ok=True)
    shade = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for y in range(0, 1000):
        sd.line([(0, y), (W, y)], fill=(0, 0, 0, int(170 * (1 - y / 1000))))
    img.alpha_composite(shade)
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(str(font_path("display")), 150)
    light, accent, dark = (hex_rgb(cfg["colors"][k]) for k in ("light", "accent", "dark"))
    lines = [ln.strip() for ln in th.get("text", m.get("hook", "")).upper().split("|") if ln.strip()]
    y = 420 - (len(lines) - 1) * 85
    for line in lines:
        segs, buf, inside = [], "", False
        for ch in line:
            if ch in "[]":
                if buf:
                    segs.append((buf, inside))
                buf, inside = "", ch == "["
            else:
                buf += ch
        if buf:
            segs.append((buf, inside))
        total = sum(d.textlength(sg, font=font) for sg, _ in segs)
        x = (W - total) / 2
        for sg, hi in segs:
            d.text((x, y), sg, font=font, fill=accent if hi else light, anchor="lm", stroke_width=10, stroke_fill=dark)
            x += d.textlength(sg, font=font)
        y += 170
    img.convert("RGB").save(out, quality=92)


def render_clip(m: Dict[str, Any], root: Optional[Path] = None, keep_work: bool = False) -> Dict[str, Any]:
    cfg_p, cfg_c = project(), channel()
    fps = int(cfg_p["fps"])
    cdir = clip_dir(m, root)
    cdir.mkdir(parents=True, exist_ok=True)
    status, blocks, flags = rights.evaluate(m)
    log: Dict[str, Any] = {"id": m["id"], "rights_status": status, "blocking": blocks, "flags": flags,
                           "rendered": False, "time": time.strftime("%Y-%m-%d %H:%M:%S")}
    if status == "BLOCKED":
        save_json(cdir / "render_log.json", log)
        return log

    src = Path(m["source"]["path"]).resolve()
    final = (cdir / "final.mp4").resolve()
    if src == final or final.parent == src.parent and src.name.startswith("final"):
        raise RuntimeError("Refusing to render over the source footage")
    info = media_info(src)
    shots = normalize_shots(m, info, src)
    work = cdir / "_work"
    if work.exists():
        shutil.rmtree(work)
    (work / "fonts").mkdir(parents=True)
    for key in ("display", "caption"):
        shutil.copy2(font_path(key), work / "fonts" / font_path(key).name)

    shot_files = []
    for i, s in enumerate(shots):
        f = work / f"shot_{i:02d}.mkv"
        ssrc, sinfo = shot_source(s, src, info)
        if ssrc == final:
            raise RuntimeError("Refusing to render over the source footage")
        _render_shot(ssrc, sinfo, m, s, f)
        shot_files.append(f)

    # Timeline (output time) including transitions.
    timeline, t_end = [], 0.0
    for i, s in enumerate(shots):
        tr = s.get("transition", "cut") if i > 0 else "cut"
        start = t_end - (XFADE_DUR if tr != "cut" else 0.0)
        s["start"], s["transition"] = start, tr
        t_end = start + s["dur"]
        timeline.append(s)
    outro_start = None
    inputs: List[Any] = []
    for f in shot_files:
        inputs += ["-i", f]
    durations = [s["dur"] for s in shots]
    use_outro = m.get("outro", cfg_c.get("outro_sting", True))
    outro_file = branding_dir() / "outro_sting.mp4"
    if use_outro and outro_file.is_file():
        inputs += ["-i", outro_file]
        od = media_info(outro_file)["duration"]
        outro_start = t_end - XFADE_DUR
        durations.append(od)
        t_end = outro_start + od
    total = t_end
    n_av = len(durations)

    cap_info = build_ass(m, timeline, total, work / "captions.ass")

    parts = []
    for i in range(n_av):
        parts.append(f"[{i}:v]fps={fps},format=yuv420p,setsar=1,setpts=PTS-STARTPTS,settb=AVTB[v{i}]")
        parts.append(f"[{i}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,asetpts=PTS-STARTPTS[a{i}]")
    cv, ca, run_t = "v0", "a0", durations[0]
    for i in range(1, n_av):
        tr = timeline[i]["transition"] if i < len(timeline) else "fade"
        if tr == "cut":
            parts.append(f"[{cv}][{ca}][v{i}][a{i}]concat=n=2:v=1:a=1[cv{i}][ca{i}]")
            run_t += durations[i]
        else:
            off = run_t - XFADE_DUR
            parts.append(f"[{cv}][v{i}]xfade=transition={tr}:duration={XFADE_DUR}:offset={off:.3f}[cv{i}]")
            parts.append(f"[{ca}][a{i}]acrossfade=d={XFADE_DUR}[ca{i}]")
            run_t += durations[i] - XFADE_DUR
        cv, ca = f"cv{i}", f"ca{i}"

    wm = cfg_c["watermark"]
    wm_idx = n_av
    inputs += ["-i", branding_dir() / "watermark.png"]
    wm_end = outro_start if outro_start is not None else total + 1
    parts.append(f"[{cv}]subtitles=filename=captions.ass:fontsdir=fonts[vs]")
    parts.append(f"[{wm_idx}:v]format=rgba,colorchannelmixer=aa={wm['opacity']}[wm]")
    parts.append(f"[vs][wm]overlay=x={wm['margin_x']}:y={wm['margin_y']}:enable='lt(t,{wm_end:.3f})',format=yuv420p[vout]")

    sfx_events = _auto_sfx(m, timeline, outro_start)
    mix_inputs = [f"[{ca}]"]
    k = wm_idx + 1
    for j, e in enumerate(sfx_events):
        sfile = branding_dir() / "sfx" / f"{e['name']}.wav"
        if not sfile.is_file():
            continue
        inputs += ["-i", sfile]
        ms = int(e["t"] * 1000)
        parts.append(f"[{k}:a]adelay={ms}|{ms},volume={e.get('gain', 0.7)}[s{j}]")
        mix_inputs.append(f"[s{j}]")
        k += 1
    music = m.get("music") or {}
    if music.get("path") and music.get("license"):
        inputs += ["-stream_loop", "-1", "-i", music["path"]]
        parts.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,volume={music.get('gain', 0.12)}[mus]")
        mix_inputs.append("[mus]")
        k += 1
    tp = cfg_p["true_peak"]
    parts.append(f"{''.join(mix_inputs)}amix=inputs={len(mix_inputs)}:normalize=0:duration=first:dropout_transition=0,"
                 f"loudnorm=I={cfg_p['target_lufs']}:TP={tp}:LRA=11,alimiter=limit={10 ** ((tp - 2.0) / 20):.3f}:level=disabled,"
                 f"aresample=48000[aout]")

    gfile = work / "assemble.graph.txt"
    gfile.write_text(";\n".join(parts), encoding="utf-8")
    tmp_out = work / "final.tmp.mp4"
    run(["ffmpeg", "-y", *inputs, "-/filter_complex", gfile.name, "-map", "[vout]", "-map", "[aout]",
         "-c:v", "libx264", *X264_LOW_MEM, "-preset", "fast", "-crf", "18", "-profile:v", "high", "-pix_fmt", "yuv420p",
         "-r", fps, "-g", fps * 2, "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
         "-t", f"{total:.3f}", "-movflags", "+faststart", tmp_out.resolve()], cwd=work)
    # loudnorm in one pass can land quiet on calm footage: measure and correct the gain (video copied).
    from .qa import _loudness
    ld = _loudness(tmp_out)
    if ld["lufs"] is not None and abs(ld["lufs"] - cfg_p["target_lufs"]) > 1.0:
        gain = cfg_p["target_lufs"] - ld["lufs"]
        fixed = work / "final.gain.mp4"
        run(["ffmpeg", "-y", "-i", tmp_out.resolve(), "-map", "0:v", "-map", "0:a", "-c:v", "copy",
             "-af", f"volume={gain:.2f}dB,alimiter=limit={10 ** ((cfg_p['true_peak'] - 2.0) / 20):.3f}:level=disabled",
             "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", fixed.resolve()])
        tmp_out = fixed
        log["loudness_gain_db"] = round(gain, 2)
    shutil.move(str(tmp_out), str(final))
    make_thumbnail(final, m, cdir / "thumbnail.jpg", total)
    shutil.copy2(work / "captions.ass", cdir / "captions.ass")

    log.update({
        "rendered": True, "duration": round(total, 3), "shots": [
            {k2: s[k2] for k2 in ("type", "in", "out", "speed", "dur", "start", "transition") if k2 in s}
            for s in timeline],
        "outro_start": outro_start, "sfx": sfx_events, "captions": cap_info,
        "source": str(src), "source_info": {k2: info[k2] for k2 in ("width", "height", "fps", "duration", "has_audio")},
    })
    save_json(cdir / "render_log.json", log)
    if not keep_work:
        shutil.rmtree(work, ignore_errors=True)
    return log
