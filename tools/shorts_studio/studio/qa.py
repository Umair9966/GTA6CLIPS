"""Automated QA for rendered Shorts. Technical checks are automated; a human still has to
watch each video before publishing (humour, context, subtitle wording)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image

from . import rights
from .common import (W, H, branding_dir, channel, clip_dir, load_json, media_info, project, run, save_json)


def _check(checks: List[Dict[str, Any]], name: str, ok: bool, detail: str, level: str = "error") -> None:
    checks.append({"check": name, "ok": bool(ok), "level": level, "detail": detail})


def _loudness(path: Path) -> Dict[str, Optional[float]]:
    err = run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"],
              check=False).stderr
    summary = err[err.rfind("Summary:"):] if "Summary:" in err else err
    i = re.search(r"I:\s+(-?[\d.]+) LUFS", summary)
    p = re.search(r"Peak:\s+(-?[\d.]+|-inf) dBFS", summary)
    return {"lufs": float(i.group(1)) if i else None,
            "true_peak": float(p.group(1)) if p and p.group(1) != "-inf" else None}


def _black_segments(path: Path) -> List[str]:
    err = run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-vf", "blackdetect=d=0.08:pix_th=0.08",
               "-an", "-f", "null", "-"], check=False).stderr
    return re.findall(r"black_start:\s*([\d.]+)\s+black_end:\s*([\d.]+)", err)


def _decode_errors(path: Path) -> List[str]:
    err = run(["ffmpeg", "-v", "error", "-i", path, "-f", "null", "-"], check=False).stderr
    return [ln for ln in err.splitlines() if ln.strip()]


def _watermark_present(path: Path, t: float, work: Path) -> Dict[str, Any]:
    cfg = channel()["watermark"]
    wm = Image.open(branding_dir() / "watermark.png").convert("RGBA")
    frame_png = work / "_qa_wm.png"
    run(["ffmpeg", "-y", "-ss", f"{t:.2f}", "-i", path, "-frames:v", "1", frame_png])
    frame = Image.open(frame_png).convert("L")
    frame_png.unlink(missing_ok=True)
    x0, y0 = cfg["margin_x"], cfg["margin_y"]
    hits = total = 0
    wl = wm.convert("LA")
    for y in range(wm.height):
        for x in range(wm.width):
            lum, a = wl.getpixel((x, y))
            if a > 230 and lum > 220:  # solid white text pixels of the watermark
                total += 1
                if frame.getpixel((x0 + x, y0 + y)) > 150:
                    hits += 1
    ratio = hits / total if total else 0.0
    return {"ok": ratio > 0.8, "ratio": round(ratio, 3), "pixels": total}


def _caption_checks(ass: Path, duration: float) -> Dict[str, Any]:
    if not ass.is_file():
        return {"ok": False, "detail": "captions.ass missing"}
    def sec(v: str) -> float:
        h, m, s = v.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)
    caps, issues = [], []
    for ln in ass.read_text(encoding="utf-8-sig").splitlines():
        if ln.startswith("Dialogue:"):
            f = ln.split(",", 9)
            s, e, style = sec(f[1]), sec(f[2]), f[3]
            if e > duration + 0.05 or s < 0:
                issues.append(f"{style} event {f[1]}-{f[2]} outside video")
            if e - s < 0.04:
                issues.append(f"{style} event {f[1]} too short")
            if style == "Caption":
                caps.append((s, e))
    caps.sort()
    overlaps = sum(1 for a, b in zip(caps, caps[1:]) if b[0] < a[1] - 0.011)
    if overlaps:
        issues.append(f"{overlaps} overlapping caption events")
    return {"ok": not issues, "detail": "; ".join(issues) or f"{len(caps)} caption events, no overlaps, all in range",
            "caption_events": len(caps)}


def qa_clip(m: Dict[str, Any], root: Optional[Path] = None) -> Dict[str, Any]:
    cfg = project()
    cdir = clip_dir(m, root)
    final = cdir / "final.mp4"
    status, blocks, flags = rights.evaluate(m)
    report: Dict[str, Any] = {"id": m["id"], "title": m.get("title"), "rights_status": status,
                              "rights_blocking": blocks, "rights_flags": flags, "checks": []}
    if not final.is_file():
        report["tech_status"] = "NOT_RENDERED"
        report["overall"] = "BLOCKED" if status == "BLOCKED" else "NOT_RENDERED"
        cdir.mkdir(parents=True, exist_ok=True)
        save_json(cdir / "qa_report.json", report)
        return report
    checks = report["checks"]
    info = media_info(final)
    v, a = info["video"], info["audio"]
    _check(checks, "resolution", (info["width"], info["height"]) == (W, H), f"{info['width']}x{info['height']}")
    sar = v.get("sample_aspect_ratio", "1:1")
    _check(checks, "aspect_ratio", sar in ("1:1", "N/A", "0:1") and info["width"] * 16 == info["height"] * 9,
           f"9:16, SAR {sar}")
    _check(checks, "frame_rate", abs(info["fps"] - cfg["fps"]) < 0.5, f"{info['fps']:.2f} fps")
    _check(checks, "codec", v.get("codec_name") == "h264" and v.get("pix_fmt") == "yuv420p",
           f"{v.get('codec_name')} {v.get('pix_fmt')}")
    d = info["duration"]
    _check(checks, "duration", cfg["duration_min"] <= d <= cfg["duration_max"],
           f"{d:.2f}s (target {cfg['duration_min']}-{cfg['duration_max']}s)")
    br = float(info["format"].get("bit_rate", 0)) / 1e6
    _check(checks, "bitrate", br >= 4.0, f"{br:.1f} Mbps", level="warning")
    _check(checks, "audio_stream", a is not None and a.get("codec_name") == "aac" and a.get("sample_rate") == "48000",
           f"{a.get('codec_name') if a else None} {a.get('sample_rate') if a else ''} Hz")
    loud = _loudness(final)
    lufs_ok = loud["lufs"] is not None and abs(loud["lufs"] - cfg["target_lufs"]) <= 2.0
    _check(checks, "loudness", lufs_ok, f"{loud['lufs']} LUFS integrated (target {cfg['target_lufs']}±2)")
    _check(checks, "true_peak", loud["true_peak"] is not None and loud["true_peak"] <= -0.5,
           f"{loud['true_peak']} dBTP")
    blacks = _black_segments(final)
    _check(checks, "black_frames", not blacks, f"{len(blacks)} black segment(s) {blacks[:3]}")
    errs = _decode_errors(final)
    _check(checks, "decode_errors", not errs, f"{len(errs)} decoder messages {errs[:2]}")
    wm = _watermark_present(final, min(1.5, d / 2), cdir)
    _check(checks, "watermark", wm["ok"], f"{wm['ratio'] * 100:.0f}% of watermark text pixels detected at expected position")
    cap = _caption_checks(cdir / "captions.ass", d)
    _check(checks, "subtitle_timing", cap["ok"], cap["detail"])
    try:
        log = load_json(cdir / "render_log.json")
        sync = log.get("captions", {}).get("caption_sync", "unknown")
    except Exception:
        sync = "unknown"
    _check(checks, "subtitle_sync_source", sync.startswith("word-level") or sync.startswith("output-time") or sync == "none",
           f"timing source: {sync}" + (" (on-screen story captions only, no speech subtitles)" if sync == "none" else ""), level="warning")
    thumb = cdir / "thumbnail.jpg"
    _check(checks, "thumbnail", thumb.is_file() and Image.open(thumb).size == (W, H), str(thumb.name))
    for doc in ("metadata.txt", "source_and_license_notes.txt"):
        _check(checks, doc, (cdir / doc).is_file(), doc)

    failed = [c for c in checks if not c["ok"] and c["level"] == "error"]
    report["tech_status"] = "PASS" if not failed else "FAIL"
    report["duration"] = round(d, 2)
    report["loudness"] = loud
    if status == "BLOCKED":
        report["overall"] = "BLOCKED"
    elif failed:
        report["overall"] = "FAILED_QA"
    elif status == "FLAGGED":
        report["overall"] = "FLAGGED_NOT_CLEARED_FOR_MONETIZED_PUBLICATION"
    else:
        report["overall"] = "READY_FOR_HUMAN_REVIEW"
    save_json(cdir / "qa_report.json", report)
    return report


def _dhash(path: Path) -> int:
    img = Image.open(path).convert("L").resize((9, 8))
    bits = 0
    for y in range(8):
        for x in range(8):
            bits = (bits << 1) | (img.getpixel((x, y)) > img.getpixel((x + 1, y)))
    return bits


def cross_clip_checks(manifests: List[Dict[str, Any]], root: Optional[Path] = None) -> List[str]:
    """Detect repeated content: overlapping source ranges and near-identical frames."""
    warnings = []
    ranges = []
    for m in manifests:
        p = (m.get("source") or {}).get("path")
        if not p:
            continue
        for s in m.get("shots", []):
            if s.get("type", "play") != "freeze":
                ranges.append((m["id"], str(Path(p).resolve()).lower(), float(s["in"]), float(s["out"])))
    for i, a in enumerate(ranges):
        for b in ranges[i + 1:]:
            if a[0] != b[0] and a[1] == b[1] and a[2] < b[3] and b[2] < a[3]:
                warnings.append(f"Clips {a[0]} and {b[0]} reuse the same source range ({max(a[2], b[2]):.1f}-{min(a[3], b[3]):.1f}s)")
    thumbs = [(m["id"], clip_dir(m, root) / "thumbnail.jpg") for m in manifests]
    hashes = [(cid, _dhash(t)) for cid, t in thumbs if t.is_file()]
    for i, (ia, ha) in enumerate(hashes):
        for ib, hb in hashes[i + 1:]:
            if bin(ha ^ hb).count("1") <= 4:
                warnings.append(f"Thumbnails of clips {ia} and {ib} are near-identical")
    return sorted(set(warnings))
