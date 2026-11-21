"""Shared paths, config loading and process helpers."""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

STUDIO_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = STUDIO_ROOT.parent
FONTS_DIR = REPO_ROOT / "backend" / "fonts"
MANIFEST_DIR = STUDIO_ROOT / "manifests"
W, H = 1080, 1920
# Keeps x264 memory modest (this machine runs close to its commit limit).
X264_LOW_MEM = ["-threads", "4", "-x264-params", "rc-lookahead=20:lookahead-threads=1"]


def load_json(path: Path | str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_json(path: Path | str, data: Any) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def project() -> Dict[str, Any]:
    return load_json(STUDIO_ROOT / "config" / "project.json")


def channel() -> Dict[str, Any]:
    return load_json(STUDIO_ROOT / "config" / "channel.json")


def out_root() -> Path:
    return Path(project()["output_root"])


def branding_dir() -> Path:
    return out_root() / "channel_branding"


def font_path(key: str) -> Path:
    return FONTS_DIR / channel()["fonts"][key]


def hex_rgb(value: str) -> tuple:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def ass_color(value: str, alpha: int = 0) -> str:
    r, g, b = hex_rgb(value)
    return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}"


def even(v: float) -> int:
    return int(round(v / 2.0)) * 2


def run(cmd: List[str], cwd: Optional[Path] = None, check: bool = True, timeout: int = 3600) -> subprocess.CompletedProcess:
    for attempt in range(4):
        proc = subprocess.run(
            [str(c) for c in cmd], cwd=cwd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
        oom = proc.returncode in (-12, 4294967284) or "malloc of size" in proc.stderr             or "Cannot allocate memory" in proc.stderr
        if proc.returncode == 0 or not oom:
            break
        time.sleep(3 * (attempt + 1))  # transient out-of-memory: wait and retry
    if check and proc.returncode != 0:
        joined = " ".join(str(c) for c in cmd)
        raise RuntimeError(f"Command failed ({proc.returncode}): {joined[:800]}\n{proc.stderr[-4000:]}")
    return proc


def ffprobe(path: Path) -> Dict[str, Any]:
    proc = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path])
    return json.loads(proc.stdout)


def media_info(path: Path) -> Dict[str, Any]:
    data = ffprobe(path)
    v = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in data["streams"] if s["codec_type"] == "audio"), None)
    if v is None:
        raise RuntimeError(f"No video stream in {path}")
    num, den = (v.get("avg_frame_rate") or v.get("r_frame_rate") or "30/1").split("/")
    fps = float(num) / float(den) if float(den) else 30.0
    return {
        "width": int(v["width"]), "height": int(v["height"]), "fps": fps,
        "duration": float(data["format"].get("duration") or v.get("duration") or 0),
        "has_audio": a is not None, "video": v, "audio": a, "format": data["format"],
    }


def load_manifests(ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    manifests = []
    for path in sorted(MANIFEST_DIR.glob("*.json")):
        m = load_json(path)
        m["_path"] = str(path)
        if not ids or m["id"] in ids:
            manifests.append(m)
    return manifests


def clip_dir(m: Dict[str, Any], root: Optional[Path] = None) -> Path:
    root = root or out_root()
    return root / project()["groups"][m["group"]] / f"{m['id']}_clip"


def require_tools() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            raise SystemExit(f"{tool} not found on PATH")
