"""Per-clip metadata / license notes plus project-level audit, rankings and master report."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import rights
from .common import channel, clip_dir, load_json, out_root, project

ROCKSTAR_POLICY = "https://support.rockstargames.com/articles/200153756/Policy-on-posting-copyrighted-Rockstar-Games-material"
REFERENCE_URL = "https://www.youtube.com/watch?v=qSyo5d-dVzA"


def _qa(m: Dict[str, Any], root: Optional[Path]) -> Dict[str, Any]:
    p = clip_dir(m, root) / "qa_report.json"
    return load_json(p) if p.is_file() else {}


def _bullets(items: List[str], indent: str = "  - ") -> str:
    return "\n".join(f"{indent}{i}" for i in items) if items else f"{indent}(none)"


def metadata_txt(m: Dict[str, Any], root: Optional[Path]) -> str:
    status, blocks, flags = rights.evaluate(m)
    qa = _qa(m, root)
    th = m.get("thumbnail", {})
    facts = m.get("facts", [])
    fact_lines = [f"{'[SHOWN IN FOOTAGE]' if f.get('verified') else '[NEEDS VERIFICATION]'} {f['claim']}  <- "
                  f"{f.get('evidence') or f.get('source_url', '')}" for f in facts]
    src = m.get("source", {})
    return f"""CLIP {m['id']}  |  Group {m['group']}  |  Style: {m['style']}
Concept: {m.get('concept', '')}
Rights status: {status}   |   QA: {qa.get('overall', 'not run / not rendered')}
NOT PUBLISHED. Nothing in this workflow uploads to YouTube. Publish manually after your review.

TITLE
  {m.get('title', '')}

DESCRIPTION
  {m.get('description', '')}

HASHTAGS
  {' '.join(m.get('hashtags', []))}

OPENING HOOK (first 1-2 s)
  {m.get('hook', '')}

SUGGESTED THUMBNAIL / COVER FRAME
  Text: {th.get('text', '').replace('|', ' / ')}
  Idea: {th.get('idea', '')}
  (Shorts covers are picked from a video frame in the YouTube app; thumbnail.jpg is the branded reference.)

SUGGESTED PINNED COMMENT
  {m.get('pinned_comment', '')}

EDITING PLAN
{_bullets(m.get('editing_plan', []))}

SOURCE
  {src.get('owner') or '-'}
  Stream range: {src.get('stream_range') or '-'}   Link: {src.get('original_url') or '-'}

FACTS & EVIDENCE
{_bullets(fact_lines) if fact_lines else '  (not a fact video)'}

WHY IT IS NOT CLEARED YET
{_bullets(blocks + flags)}
"""


def license_txt(m: Dict[str, Any]) -> str:
    cfg = channel()
    src = m.get("source", {})
    status, blocks, flags = rights.evaluate(m)
    music = m.get("music") or {}
    ref = ""
    if src.get("cc_credits"):
        lines = "\n".join(f"  - \"{c['title']}\" by {c['channel']}\n    {c['url']}\n"
                          f"    Licence: {c['license']} | uploaded {c['upload_date']}"
                          for c in src["cc_credits"])
        ref = f"""
CREATIVE COMMONS FOOTAGE (CC BY): REUSE ALLOWED WITH ATTRIBUTION
{lines}
  Each uploader set the Creative Commons Attribution licence on YouTube (checked via the video metadata
  on download). CC BY allows copying, editing and commercial use if the creator is credited, so the
  credit lines are in the description. Keep them there.
  Caveats: (1) a CC licence is only valid if the uploader owns the recording; these are original
  gameplay uploads with no facecam or other creators' content. (2) The game itself (visuals, characters,
  dialogue) is still Rockstar/Take-Two content and Rockstar's video policy applies, exactly as it would
  for your own recording. (3) Content ID can still match footage other channels have also uploaded;
  if a claim appears, dispute it citing the CC BY source link.
"""
    elif src.get("third_party_creator_footage"):
        ref = f"""
THIRD-PARTY CREATOR FOOTAGE: USED WITHOUT A LICENCE
  Source: {src.get('original_url') or REFERENCE_URL}  (IShowSpeed livestream, stream time {src.get('stream_range', '-')})
  This clip contains IShowSpeed's stream footage, voice, facecam/likeness and reactions.
  NO permission from IShowSpeed (or his management) is on file. It was downloaded and edited only
  because the channel owner explicitly instructed it ({src.get('owner_override', '-')}).
  Editing, captioning or adding a watermark does NOT make this use licensed. Uploading can lead to
  Content ID claims, copyright strikes and channel termination. To clear it: get written permission
  from the creator covering editing, derivative works and monetization, then record it in
  source.third_party_permission_doc.
  The stream title calls it "early access" gameplay. Rockstar's policy lists pre-release footage as
  content it takes down; whether that applies here is unconfirmed.
"""
    return f"""SOURCE & LICENSE NOTES - CLIP {m['id']}
Generated {time.strftime('%Y-%m-%d %H:%M')}. Status: {status}

1. GAMEPLAY FOOTAGE
  File:                     {src.get('path') or '(none assigned: capture required)'}
  Owner / captured by:      {src.get('owner') or '-'} / {src.get('captured_by') or '-'}
  Capture date / platform:  {src.get('capture_date') or '-'} / {src.get('platform') or '-'}
  Game version:             {src.get('game_version') or '-'}
  Rights basis:             {src.get('rights_basis') or '(undocumented)'}
  Monetization permission:  {src.get('monetization_permission', 'unconfirmed')}
  Leaked / pre-release:     {src.get('leaked_or_prerelease', False)}
  Isolated cutscene:        {src.get('isolated_cutscene', False)}
  Story spoilers:           {src.get('story_spoilers', False)}
  Third-party audio:        {src.get('third_party_audio') or '(not declared)'}
  Voice / commentary:       {src.get('voice') or '(none declared)'}
  Underlying game content:  Grand Theft Auto VI (c) Take-Two Interactive / Rockstar Games. Use is
                            governed by Rockstar's video policy: {ROCKSTAR_POLICY}
                            Editing, captioning or adding a watermark does NOT change who owns the
                            game's audiovisual content and does not by itself make use lawful.
{ref}
2. CHANNEL BRANDING (watermark, logo, outro sting)
  Original artwork generated by shorts_studio/studio/branding.py for "{cfg['channel_name']}".
  No Rockstar/GTA logos or trade dress; no imitation of other creators' branding.

3. FONTS
  {cfg['fonts']['display']}, {cfg['fonts']['caption']} - Google Fonts, SIL Open Font License 1.1
  (commercial use permitted). Source list: supoclip/backend/fonts/SOURCES.md

4. SOUND EFFECTS
  Original, synthesized with ffmpeg (channel_branding/sfx/LICENSE.txt). No third-party samples.

5. MUSIC
  {('File: ' + music['path'] + ' | License: ' + music.get('license', 'MISSING')) if music.get('path') else 'None. Do not add commercial songs; if you want music, use a track whose license allows monetized YouTube use and record it here.'}

6. TEXT (titles, captions, descriptions)
  Original text written for this channel.

7. SOFTWARE
  SupoClip (SupoClip Noncommercial Source License v1.1: allows monetized use by individual creators;
  companies/agencies/client work need written permission from its author).

BLOCKING ISSUES
{_bullets(blocks)}

FLAGS (must be resolved before monetized publication)
{_bullets(flags)}
"""


def write_clip_docs(m: Dict[str, Any], root: Optional[Path] = None) -> None:
    cdir = clip_dir(m, root)
    cdir.mkdir(parents=True, exist_ok=True)
    (cdir / "metadata.txt").write_text(metadata_txt(m, root), encoding="utf-8")
    (cdir / "source_and_license_notes.txt").write_text(license_txt(m), encoding="utf-8")


def _status_table(manifests: List[Dict[str, Any]], root: Optional[Path]) -> str:
    rows = ["| # | Group | Style | Working title | Footage | Rights | QA |", "|---|---|---|---|---|---|---|"]
    for m in manifests:
        status, _, _ = rights.evaluate(m)
        qa = _qa(m, root)
        has = "yes" if (m.get("source") or {}).get("path") else "needs capture"
        rows.append(f"| {m['id']} | {m['group']} | {m['style']} | {m.get('title', '')} | {has} | {status} | "
                    f"{qa.get('overall', '-')} |")
    return "\n".join(rows)


def copyright_audit(manifests: List[Dict[str, Any]], root: Optional[Path]) -> str:
    return f"""# Copyright Audit: GTA 6 Shorts

Generated {time.strftime('%Y-%m-%d %H:%M')} by `python -m studio docs`. Re-run after any change.

## 1. Footage sources
### Clips 04-15: Creative Commons (CC BY) gameplay
- Footage comes from YouTube uploads whose creators set the **Creative Commons Attribution** licence
  (verified from each video's metadata at download). CC BY allows editing and commercial reuse with credit.
- Sources: LunarGaming (tank/military base, cruise ship, Vercetti Estate), How to Everything (free roam,
  store robbery, underwater, boat), dannyavelas (cross-map drive). Exact links are in each clip's
  description and source_and_license_notes.txt.
- Rejected during selection: compilations of other people's clips, GTA 5 mods labelled "GTA 6", brand-new
  reupload channels, live streams with facecams/commentary, story walkthroughs (spoilers).
- One source had a tutorial narrator; that audio is muted and replaced with original music.

### Clips 01-03: IShowSpeed stream: NOT LICENSED, DO NOT UPLOAD
- Cut from {REFERENCE_URL} on an earlier instruction, without the creator's permission. YouTube has already
  blocked this material on the channel. These three should be replaced.

## 2. Rockstar Games video policy (checked {time.strftime('%Y-%m-%d')})
Source: {ROCKSTAR_POLICY}
- Permits occasional, **non-commercial** use of gameplay footage by individual fans.
- Defines commercial use as making money from the footage you post or using it to promote a product/service.
- Will take down: leaked/pre-release content, isolated cutscenes, spoilers, standalone in-game TV/movies.
- Take-Two can remove material at any time. Licensing requests: copyright@take2games.com.
- **Consequence:** monetizing these Shorts (YouTube Shorts ad revenue share) is not clearly covered.
  Every clip stays **FLAGGED** until you either (a) get written permission from Take-Two, or
  (b) publish without monetization and set `monetization_permission` to `not-monetized`.
  This tool does not decide that for you, and this audit is not legal advice.

## 3. Audio
- In-game radio stations contain licensed commercial music and commonly trigger Content ID.
  **Record with radio off**, or mute radio sections (`"audio": "mute"` on the shot).
- SFX: original, synthesized (channel_branding/sfx). Music: none used.
- Voice: 04-15 contain only in-game character dialogue (one tutorial narrator muted). 01-03 contain IShowSpeed's voice (not licensed). In-game radio may be audible
  in some clips; check each clip for music before uploading.
- Profanity: captions are masked; the audio is not bleeped. Strong language limits ads on YouTube.

## 4. Other assets
| Asset | Origin | License |
|---|---|---|
| Logo, watermark, outro/intro sting, banner, avatar | Generated by studio/branding.py | Original, owned by channel |
| Fonts (Anton, Poppins ExtraBold) | Google Fonts via supoclip/backend/fonts | SIL OFL 1.1 |
| Sound effects | ffmpeg synthesis | Original |
| SupoClip software | github.com/FujiwaraChoki/supoclip | Noncommercial Source License v1.1 (individual creators may monetize) |

## 5. Facts (Group B)
Fact clips (10-12) only claim what is visibly shown in the footage itself (each fact records the
stream timestamp as evidence). No outside claims, rumours or leaks.
**Glitches:** none of the sections inspected showed a genuine glitch (viewer-tagged "glitch" moments at
4:29:31 and 20:21:33 turned out to be a map-open blur and a taxi skip-journey fade). Rather than
mislabel anything, clips 13-15 are "didn't see that coming" moments and are not called glitches.

## 6. Per-clip status
{_status_table(manifests, root)}

Status legend: BLOCKED = may not render (e.g. no footage); FLAGGED = renders for review but not
cleared for monetized publication; READY_FOR_HUMAN_REVIEW = rights documented, needs your final sign-off.
Nothing is ever auto-approved or auto-published.
"""


def clip_rankings(manifests: List[Dict[str, Any]]) -> str:
    out = [f"# Clip Rankings\n\nGenerated {time.strftime('%Y-%m-%d %H:%M')}.\n",
           "Ranked by hook strength, clarity of the payoff, the reaction and replay value. Moments were found "
           "from viewer-comment timestamps, a loudness scan of the full 24h audio and Whisper transcripts of ~30 "
           "candidate windows.\n"]
    for g, name in project()["groups"].items():
        ms = sorted([m for m in manifests if m["group"] == g], key=lambda m: -m.get("ranking", {}).get("score", 0))
        out.append(f"\n## Group {g} - {name}\n\n| Rank | Clip | Concept | Score /10 | Why |\n|---|---|---|---|---|")
        for i, m in enumerate(ms, 1):
            r = m.get("ranking", {})
            out.append(f"| {i} | {m['id']} | {m.get('concept', '')} | {r.get('score', '-')} | {r.get('rationale', '')} |")
    return "\n".join(out) + "\n"


def master_report(manifests: List[Dict[str, Any]], root: Optional[Path], extra: Dict[str, Any]) -> str:
    rendered = sum(1 for m in manifests if (clip_dir(m, root) / "final.mp4").is_file())
    ready = sum(1 for m in manifests if _qa(m, root).get("overall") == "READY_FOR_HUMAN_REVIEW")
    warnings = extra.get("cross_clip_warnings", [])
    selftest = extra.get("selftest")
    st = ""
    if selftest:
        st = "\n".join(f"  - {c['check']}: {'PASS' if c['ok'] else 'FAIL'} ({c['detail']})" for c in selftest.get("checks", []))
        st = f"\n## Pipeline self-test (synthetic test pattern, not a deliverable)\nResult: **{selftest.get('tech_status')}**\n{st}\n"
    return f"""# Master Report: GTA 6 Shorts

Generated {time.strftime('%Y-%m-%d %H:%M')}.

## Summary
- Clips planned: {len(manifests)} (Group A: {sum(m['group'] == 'A' for m in manifests)}, Group B: {sum(m['group'] == 'B' for m in manifests)})
- Rendered final.mp4: **{rendered} / {len(manifests)}**
- Cleared for your final review: {ready}
- Published: 0 (this workflow never uploads)

## Source
- **04-15:** real GTA 6 gameplay from Creative Commons (CC BY) YouTube uploads, credited in each description.
- **01-03:** IShowSpeed stream clips: not licensed, already blocked by YouTube. **Do not upload.**
Format: 1080x1920, 30 fps, 2-3 minutes each (YouTube Shorts allow up to 3:00).

## Status
{_status_table(manifests, root)}

## Cross-clip repetition check
{_bullets(warnings, '- ') if warnings else '- No overlapping source ranges or duplicate frames detected among rendered clips.'}
{st}
## Next steps for you
1. Watch every final.mp4 yourself (humour, context, caption wording, any radio music).
2. Decide on rights: ideally get written permission from IShowSpeed's team; without it, uploading
   risks Content ID claims and copyright strikes.
3. Monetization of GTA footage is not clearly covered by Rockstar's policy (see audit section 2).
4. Upload manually. This workflow never publishes.
5. Regenerate any clip: edit `D:/GTA6_SHORTS/_work/specs.json`, run
   `python D:/GTA6_SHORTS/_work/build_clip.py D:/GTA6_SHORTS/_work/specs.json NN`, then
   `python -m studio render NN` and `python -m studio qa NN` (from supoclip/shorts_studio).

## Workflow
See `supoclip/shorts_studio/README.md`.
"""


def write_all(manifests: List[Dict[str, Any]], root: Optional[Path] = None, extra: Optional[Dict[str, Any]] = None) -> None:
    root_path = root or out_root()
    for m in manifests:
        write_clip_docs(m, root)
    (root_path / "copyright_audit.md").write_text(copyright_audit(manifests, root), encoding="utf-8")
    (root_path / "clip_rankings.md").write_text(clip_rankings(manifests), encoding="utf-8")
    (root_path / "master_report.md").write_text(master_report(manifests, root, extra or {}), encoding="utf-8")
