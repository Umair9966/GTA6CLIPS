"""Find candidate highlight moments in YOUR OWN long gameplay capture.

Heuristic: loud reaction spikes (your commentary / crashes / gunfire) combined with bursts of
visual change (crashes, chases, explosions). It proposes windows; a human picks the final
moments and writes in/out points into a manifest. For speech-heavy captures you can also run
the capture through the SupoClip web app (upload, AI selection, GAMING_LAYOUT=auto) and use
its exported clips as sources here.
"""
from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Dict, List

from .common import media_info, run, save_json

WINDOW = 0.5


def _rms_series(src: Path) -> List[float]:
    proc = run(["ffmpeg", "-hide_banner", "-nostats", "-i", src, "-vn", "-ac", "1", "-ar", "48000", "-af",
                f"asetnsamples={int(48000 * WINDOW)},astats=metadata=1:reset=1,"
                "ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-", "-f", "null", "-"], check=False)
    vals = [float(v) if v not in ("-inf", "inf", "nan") else -90.0
            for v in re.findall(r"RMS_level=(-?[\w.]+)", proc.stdout)]
    return vals


def _scene_times(src: Path) -> List[float]:
    proc = run(["ffmpeg", "-hide_banner", "-nostats", "-i", src, "-an", "-vf",
                "fps=10,scale=320:-2,select='gt(scene,0.25)',metadata=print:file=-", "-f", "null", "-"], check=False)
    return [float(t) for t in re.findall(r"pts_time:([\d.]+)", proc.stdout)]


def scan(src: Path, top: int = 12, min_gap: float = 20.0) -> Dict[str, Any]:
    info = media_info(src)
    dur = info["duration"]
    n = max(1, int(dur / WINDOW))
    rms = _rms_series(src) if info["has_audio"] else []
    rms = (rms + [-90.0] * n)[:n]
    mean = sum(rms) / n
    sd = math.sqrt(sum((r - mean) ** 2 for r in rms) / n) or 1.0
    scenes = [0] * n
    for t in _scene_times(src):
        idx = min(n - 1, int(t / WINDOW))
        scenes[idx] += 1
    score = []
    for i in range(n):
        lo, hi = max(0, i - 4), min(n, i + 5)
        audio_z = (max(rms[lo:hi]) - mean) / sd
        visual = sum(scenes[lo:hi])
        score.append(audio_z + 0.6 * visual)
    order = sorted(range(n), key=lambda i: score[i], reverse=True)
    picks: List[Dict[str, Any]] = []
    for i in order:
        t = i * WINDOW
        if any(abs(t - p["peak"]) < min_gap for p in picks):
            continue
        picks.append({"peak": round(t, 2), "score": round(score[i], 2),
                      "suggested_in": round(max(0.0, t - 14), 2), "suggested_out": round(min(dur, t + 10), 2)})
        if len(picks) >= top:
            break
    result = {"source": str(src), "duration": round(dur, 2), "candidates": picks,
              "note": "Heuristic only (loudness spikes + visual change). Watch each window and pick manually."}
    out = src.with_name(src.stem + ".candidates.json")
    try:
        save_json(out, result)
        result["written_to"] = str(out)
    except OSError:
        pass
    return result
