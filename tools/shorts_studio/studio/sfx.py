"""Original sound effects synthesized with ffmpeg's lavfi sources.

Generated from math expressions and noise, so no samples or third-party recordings
are involved. The channel owns these outright.
"""
from __future__ import annotations

from pathlib import Path

from .common import run

SFX = {
    "whoosh": ("anoisesrc=d=0.5:c=pink:r=48000:a=0.9,highpass=f=300,lowpass=f=5000,"
               "afade=t=in:d=0.25:curve=exp,afade=t=out:st=0.25:d=0.25:curve=exp,volume=1.6", 0.5),
    "hit": ("aevalsrc=exprs='0.95*sin(2*PI*(62*t-28*t*t))*exp(-7*t)':c=stereo:s=48000:d=0.6", 0.6),
    "pop": ("aevalsrc=exprs='0.6*sin(2*PI*(700*t+5000*t*t))*exp(-40*t)':c=stereo:s=48000:d=0.12", 0.12),
    "riser": ("aevalsrc=exprs='0.35*sin(2*PI*(150*t+500*t*t))*(t/1.2)':c=stereo:s=48000:d=1.2", 1.2),
    "ding": ("aevalsrc=exprs='0.4*(sin(2*PI*1320*t)+0.5*sin(2*PI*1980*t))*exp(-5*t)':c=stereo:s=48000:d=0.8", 0.8),
    "glitch": ("aevalsrc=exprs='0.3*sgn(sin(2*PI*(110+300*mod(floor(t*30),3))*t))*lt(mod(t*30,1),0.6)'"
               ":c=stereo:s=48000:d=0.45", 0.45),
    "rewind": ("aevalsrc=exprs='0.4*sin(2*PI*(1600*t-1300*t*t))*(1-t/0.6)':c=stereo:s=48000:d=0.6", 0.6),
    "tick": ("aevalsrc=exprs='0.5*sin(2*PI*2000*t)*exp(-80*t)':c=stereo:s=48000:d=0.06", 0.06),
}


def build_sfx(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, (graph, dur) in SFX.items():
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", graph, "-t", f"{dur}", "-ac", "2", "-ar", "48000",
             "-c:a", "pcm_s16le", out_dir / f"{name}.wav"])
    (out_dir / "LICENSE.txt").write_text(
        "All files in this folder were synthesized from mathematical expressions and generated noise\n"
        "using ffmpeg lavfi sources (see shorts_studio/studio/sfx.py). They contain no third-party\n"
        "samples or recordings and are original works of the channel owner.\n",
        encoding="utf-8",
    )
