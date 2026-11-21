"""python -m studio <command>

  brand              generate channel branding + original SFX into <output_root>/channel_branding
  init               create the output tree and write all docs (no rendering)
  scan FILE          propose highlight windows in your own long capture
  render [IDS...]    render clips (all if none given); BLOCKED clips are skipped with reasons
  qa [IDS...]        run technical + rights QA
  docs               regenerate metadata, license notes, audit, rankings, master report
  all                render + docs + qa + docs for every clip
  selftest           prove the pipeline on a synthetic test pattern (not a deliverable)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import docs, qa, render
from .common import X264_LOW_MEM, load_json, load_manifests, out_root, project, require_tools, run, save_json


def _ensure_tree() -> None:
    root = out_root()
    for g in project()["groups"].values():
        (root / g).mkdir(parents=True, exist_ok=True)
    Path(project()["source_footage_dir"]).mkdir(parents=True, exist_ok=True)


def _ensure_brand() -> None:
    from .common import branding_dir
    if not (branding_dir() / "watermark.png").is_file():
        from .branding import build_all
        build_all()


def cmd_render(ids):
    _ensure_brand()
    results = []
    for m in load_manifests(ids):
        try:
            log = render.render_clip(m)
        except Exception as exc:  # report and continue with the rest of the batch
            log = {"id": m["id"], "rendered": False, "error": str(exc)[-1500:]}
        state = "rendered" if log.get("rendered") else (log.get("rights_status") or "ERROR")
        print(f"[{m['id']}] {state}" + (f" ({log.get('duration')}s)" if log.get("rendered") else ""))
        for reason in log.get("blocking", []):
            print(f"      - {reason}")
        if log.get("error"):
            print(f"      ! {log['error'][:600]}")
        results.append(log)
    return results


def cmd_qa(ids):
    manifests = load_manifests(ids)
    for m in manifests:
        r = qa.qa_clip(m)
        print(f"[{m['id']}] {r['overall']}")
        for c in r.get("checks", []):
            if not c["ok"]:
                print(f"      {c['level'].upper()}: {c['check']} - {c['detail']}")
    warnings = qa.cross_clip_checks(load_manifests())
    for w in warnings:
        print(f"  WARNING: {w}")
    return warnings


def cmd_docs(warnings=None):
    extra = {"cross_clip_warnings": warnings or []}
    st = out_root() / "_pipeline_selftest" / "selftest_qa.json"
    if st.is_file():
        extra["selftest"] = load_json(st)
    docs.write_all(load_manifests(), extra=extra)
    print(f"docs written under {out_root()}")


SELFTEST_MANIFEST = {
    "id": "00", "group": "A", "style": "funny", "concept": "Pipeline self-test",
    "title": "PIPELINE SELF-TEST (synthetic pattern)", "hook": "PIPELINE [SELF-TEST]",
    "framing": "blur",
    "source": {"owner": "channel owner", "captured_by": "ffmpeg testsrc2 (generated locally)",
               "rights_basis": "Synthetic test pattern generated locally; no third-party content",
               "monetization_permission": "not-monetized", "third_party_audio": "none", "voice": "none"},
    "shots": [
        {"type": "play", "in": 0, "out": 7, "zoom": [1.0, 1.25]},
        {"type": "freeze", "at": 6.9, "dur": 0.9, "label": "WAIT FOR IT..."},
        {"type": "play", "in": 7, "out": 14, "transition": "fade", "fx": ["shake"]},
        {"type": "replay", "in": 11, "out": 13, "speed": 0.5, "transition": "slideup"},
        {"type": "play", "in": 14, "out": 22, "framing": "fill", "transition": "zoomin", "fx": ["glitch"]},
    ],
    "texts": [{"t0": 0, "t1": 2.4, "style": "hook", "text": "PIPELINE [SELF-TEST]"},
              {"t0": 30, "t1": 33, "style": "card", "text": "Synthetic test pattern - not a real clip"}],
    "captions": [{"src": [0.5, 3.5], "text": "this is a synthetic test pattern"},
                 {"src": [4, 6.8], "text": "checking captions zoom and freeze frames"},
                 {"src": [7.5, 11], "text": "then a crossfade with camera shake"},
                 {"src": [14.5, 18], "text": "and a full screen crop at the end"}],
    "thumbnail": {"text": "PIPELINE|[SELF-TEST]", "time": 3.0},
}


def cmd_selftest():
    _ensure_brand()
    root = out_root() / "_pipeline_selftest"
    src_dir = root / "source"
    src_dir.mkdir(parents=True, exist_ok=True)
    src = src_dir / "synthetic_test_pattern.mp4"
    if not src.is_file():
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=60:duration=30",
             "-f", "lavfi", "-i", "sine=frequency=330:beep_factor=4:duration=30:sample_rate=48000",
             "-c:v", "libx264", *X264_LOW_MEM, "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ac", "2", src])
    m = json.loads(json.dumps(SELFTEST_MANIFEST))
    m["source"]["path"] = str(src)
    log = render.render_clip(m, root=root)
    if not log.get("rendered"):
        print(json.dumps(log, indent=2))
        sys.exit(1)
    docs.write_clip_docs(m, root)
    report = qa.qa_clip(m, root=root)
    save_json(root / "selftest_qa.json", report)
    print(f"selftest render: {log['duration']}s -> tech {report['tech_status']} / overall {report['overall']}")
    for c in report["checks"]:
        print(f"  {'PASS' if c['ok'] else c['level'].upper():8} {c['check']}: {c['detail']}")
    return report


def main(argv=None):
    require_tools()
    p = argparse.ArgumentParser(prog="studio", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("brand")
    sub.add_parser("init")
    s = sub.add_parser("scan"); s.add_argument("file"); s.add_argument("--top", type=int, default=12)
    r = sub.add_parser("render"); r.add_argument("ids", nargs="*")
    q = sub.add_parser("qa"); q.add_argument("ids", nargs="*")
    sub.add_parser("docs")
    sub.add_parser("all")
    sub.add_parser("selftest")
    a = p.parse_args(argv)

    if a.cmd == "brand":
        from .branding import build_all
        print(f"branding written to {build_all()}")
    elif a.cmd == "init":
        _ensure_tree(); _ensure_brand(); cmd_docs()
    elif a.cmd == "scan":
        from .scan import scan
        print(json.dumps(scan(Path(a.file), top=a.top), indent=2))
    elif a.cmd == "render":
        _ensure_tree(); cmd_render(a.ids); cmd_docs()
    elif a.cmd == "qa":
        w = cmd_qa(a.ids); cmd_docs(w)
    elif a.cmd == "docs":
        cmd_docs()
    elif a.cmd == "all":
        _ensure_tree(); cmd_render([]); cmd_docs(); w = cmd_qa([]); cmd_docs(w)
    elif a.cmd == "selftest":
        cmd_selftest(); cmd_docs()
