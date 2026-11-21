"""Build Shorts Studio manifests (04-15) from CC BY-licensed GTA 6 gameplay.

usage: python build_cc.py 04 05 ...
Writes D:/Git/supoclip/shorts_studio/manifests/NN.json and an original music bed per clip.
"""
import json, sys, textwrap
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_video import synth_music, wav_write  # original synthesized music

HERE = Path(__file__).resolve().parent
P = json.loads((HERE / "plans.json").read_text(encoding="utf-8"))
SRC_DIR = Path("D:/GTA6_SHORTS/_source_footage/cc")
MAN = Path("D:/Git/supoclip/shorts_studio/manifests")
MUSIC_DIR = Path("D:/GTA6_SHORTS/channel_branding/music")
TARGET = 150.0     # seconds of gameplay before freeze/replay/outro
REPLAY = 4.0


def wrap(t, n=22):
    return "\n".join(textwrap.wrap(t, n))


def info(key):
    vid, ch = P["_sources"][key]
    meta = json.loads((SRC_DIR / f"{vid}.info.json").read_text(encoding="utf-8"))
    return vid, ch, meta


def build(cid):
    plan = P[cid]
    segs = [list(s) for s in plan["segs"]]
    total = sum((s[2] - s[1]) / s[3] for s in segs)
    f = min(1.0, TARGET / total)
    if total * f < 115:
        raise SystemExit(f"{cid}: only {total:.0f}s planned")
    shots, texts, t_out = [], [], 0.0
    pk_key, pk_t = plan["peak"]
    mute = set(plan.get("mute", []))
    zoom = plan.get("zoom", 1.0)
    focus = plan.get("focus", [0.5, 0.5])
    for i, (key, a, b, spd, cap) in enumerate(segs):
        L = (b - a) * f
        c = (a + b) / 2
        a2, b2 = c - L / 2, c + L / 2
        if key == pk_key and a <= pk_t <= b:   # keep the peak inside the trimmed range
            if pk_t < a2: a2, b2 = max(a, pk_t - 1.0), max(a, pk_t - 1.0) + L
            if pk_t > b2: b2 = min(b, pk_t + 1.5); a2 = b2 - L
        vid = P["_sources"][key][0]
        z = zoom if key == "drive" else ([1.0, 1.0] if i % 3 == 0 else [1.0, 1.07] if i % 3 == 1 else [1.08, 1.08])
        shot = {"type": "play", "src": str(SRC_DIR / f"{vid}.mp4").replace("\\", "/"), "in": round(a2, 2), "out": round(b2, 2),
                "speed": spd, "zoom": [z, z] if isinstance(z, float) else z, "focus": focus if key == "drive" else [0.5, 0.5],
                "audio": "mute" if (key in mute or spd > 1.5) else plan.get("audio", "keep")}
        if i and shots:
            shot["transition"] = "fade" if i % 4 == 0 else "cut"
        dur = (b2 - a2) / spd
        texts.append({"t0": round(t_out + 0.15, 2), "t1": round(t_out + min(dur, 4.0), 2), "style": "card", "text": wrap(cap)})
        shots.append(shot)
        t_out += dur - (0.2 if shot.get("transition", "cut") != "cut" else 0)
        # freeze + replay right after the shot holding the peak
        if key == pk_key and a2 <= pk_t <= b2:
            src = shot["src"]
            shots.append({"type": "freeze", "src": src, "at": round(min(pk_t, b2 - 0.05), 2), "dur": 0.9,
                          "label": plan.get("freeze_label", "WAIT WHAT")})
            shots.append({"type": "replay", "src": src, "in": round(pk_t - REPLAY / 2, 2), "out": round(pk_t + REPLAY / 2, 2),
                          "speed": 0.5, "transition": "fade", "fx": ["highlight", "flash"],
                          "audio": "mute" if key in mute else "keep"})
            t_out += 0.9 + REPLAY / 0.5 - 0.2
    if plan.get("end_label"):
        shots[-1]["label"] = plan["end_label"]
    # cold open: 2.2 s flash-forward of the peak under the hook
    pk_src = str(SRC_DIR / f"{P['_sources'][pk_key][0]}.mp4").replace("\\", "/")
    shots.insert(0, {"type": "replay", "src": pk_src, "in": round(pk_t - 1.2, 2), "out": round(pk_t + 1.0, 2), "speed": 1.0,
                     "label": "", "fx": ["flash"], "zoom": [1.0, 1.12],
                     "audio": "mute" if pk_key in mute else plan.get("audio", "keep")})
    shots[1]["transition"] = "fade"
    for tx in texts:
        tx["t0"] += 2.0; tx["t1"] += 2.0
    t_out += 2.0
    texts.insert(0, {"t0": 0.0, "t1": 2.4, "style": "hook", "text": plan["hook"]})

    # original music bed
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    mpath = MUSIC_DIR / f"bed_{cid}.wav"
    music = synth_music(t_out + 4, int(cid) + 7)
    wav_write(mpath, np.stack([music, music], 1))

    keys = sorted({s[0] for s in segs} | {pk_key})
    credits = []
    for k in keys:
        vid, ch, meta = info(k)
        credits.append({"video_id": vid, "channel": ch, "title": meta.get("title"), "url": f"https://www.youtube.com/watch?v={vid}",
                        "license": meta.get("license"), "upload_date": meta.get("upload_date"), "channel_url": meta.get("channel_url")})
    primary = keys[0] if pk_key not in keys else pk_key
    pvid = P["_sources"][primary][0]
    credit_lines = "\n".join(f"- \"{c['title']}\" by {c['channel']}: {c['url']} (licensed CC BY)" for c in credits)
    m = json.loads((MAN / f"{cid}.json").read_text(encoding="utf-8"))
    m.update({
        "id": cid, "group": plan["group"], "style": plan["style"], "concept": plan["title"], "title": plan["title"],
        "description": (f"{plan['title']}\n\nGameplay footage used under the Creative Commons Attribution licence (CC BY). Credit:\n"
                        f"{credit_lines}\n\nEdited by this channel with original captions, music and effects. Grand Theft Auto VI "
                        "(c) Rockstar Games / Take-Two Interactive. Not affiliated with Rockstar, Take-Two or the credited creators."),
        "hashtags": plan["tags"], "hook": plan["hook"].replace("[", "").replace("]", ""),
        "thumbnail": {"text": plan["thumb"], "time": round(t_out * plan.get("thumb_t", 0.4), 2),
                      "idea": "Frame from the action peak with bold two-line text."},
        "pinned_comment": plan["pinned"],
        "editing_plan": [
            "0-2.2s cold open: flash-forward of the peak moment under the hook text",
            "Gameplay panel over a blurred, colour-boosted copy of the same shot (keeps the full 16:9 action visible in 9:16)",
            "Story told in short captions, one beat per shot; slow parts trimmed; alternating punch-in zooms",
            f"Peak moment: freeze frame + '{plan.get('freeze_label', '')}' label, then 0.5x replay with highlight border",
            "Original synthwave music bed under the game audio; original whoosh/hit/rewind SFX on cuts",
            "Ends on the outro sting for a loop back to the cold open"],
        "ranking": {"score": 0, "rationale": ""},
        "source": {
            "path": str(SRC_DIR / f"{pvid}.mp4").replace("\\", "/"),
            "owner": "; ".join(f"{c['channel']} ({c['video_id']})" for c in credits),
            "captured_by": ", ".join(sorted({c["channel"] for c in credits})),
            "capture_date": ", ".join(sorted({c["upload_date"] or "" for c in credits})),
            "platform": "YouTube uploads licensed CC BY (Creative Commons Attribution)",
            "game_version": "GTA VI retail (released Nov 19, 2026)",
            "rights_basis": "Creative Commons Attribution licence set by each uploader (verified via YouTube metadata); attribution in description",
            "monetization_permission": "unconfirmed",
            "leaked_or_prerelease": False, "isolated_cutscene": False, "story_spoilers": False,
            "third_party_creator_footage": True,
            "third_party_permission_doc": "CC BY licence on each source video: " + ", ".join(c["url"] for c in credits),
            "third_party_audio": "none detected (in-game dialogue/SFX only; no song lyrics found by transcription)",
            "voice": "in-game character dialogue only" + ("; source narrator muted" if mute else ""),
            "cc_credits": credits},
        "framing": "blur", "auto_sfx": True, "shots": shots, "texts": texts, "captions": [], "words": [], "sfx": [],
        "caption_y": 1640, "label_y": 1180, "card_y": 1650,
        "music": {"path": str(mpath).replace("\\", "/"), "license": "Original, synthesized in code (make_video.synth_music)",
                  "gain": 0.3 if any(s.get("audio") == "mute" for s in shots[1:]) else 0.13},
        "facts": [], "glitch_reproduced_in_footage": False,
    })
    for k in ("cam", "cam_panel_h", "capture_brief"):
        m.pop(k, None)
    (MAN / f"{cid}.json").write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{cid}: {len(shots)} shots, ~{t_out + 1.2:.0f}s")


if __name__ == "__main__":
    for c in sys.argv[1:]:
        build(c)
