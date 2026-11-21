# Shorts Studio: GTA 6 Shorts production layer for SupoClip

A finishing layer on top of SupoClip. SupoClip finds and cuts moments from long videos; Shorts
Studio adds a consistent, rights-gated, branded, QA-checked edit and full publishing paperwork.
Outputs go to `D:/GTA6_SHORTS` (set in `config/project.json`).

```
cd D:\Git\supoclip\shorts_studio
python -m studio brand            # logo, watermark, banner, avatar, stings, original SFX
python -m studio init             # output tree + all docs
python -m studio scan D:\GTA6_SHORTS\_source_footage\session1.mp4   # candidate moments
python -m studio render 03        # render one clip (or several: render 01 03 05)
python -m studio qa 03            # technical + rights QA
python -m studio all              # render + QA + docs for all 15
python -m studio selftest         # prove the pipeline on a synthetic test pattern
```
Requirements: Python 3.11 + Pillow, ffmpeg/ffprobe on PATH (ffmpeg 7+ for `-/filter_complex`).

## Rights gate (studio/rights.py)
| Status | Meaning |
|---|---|
| `BLOCKED` | Will not render: no footage, undocumented rights, a URL source (never downloaded), leaked/pre-release footage, isolated cutscenes, another creator's footage without written permission, or unlicensed music |
| `FLAGGED` | Renders for review, but is **not** cleared for monetized publication: monetization permission unconfirmed, radio/music audio, spoilers, unverified facts, or an unconfirmed glitch |
| `READY_FOR_HUMAN_REVIEW` | Rights documented; you still watch it and sign off |

Nothing is ever auto-approved or uploaded.

## Making a clip
1. Record your own gameplay (in-game radio **off**, free-roam, no story spoilers) into `D:/GTA6_SHORTS/_source_footage/`.
2. `python -m studio scan <file>` lists loud/high-action windows. Watch them and choose.
3. Edit `manifests/NN.json`:
```jsonc
"source": {
  "path": "D:/GTA6_SHORTS/_source_footage/session1.mp4",
  "owner": "<you>", "captured_by": "<you>", "capture_date": "2026-11-21",
  "platform": "PS5", "game_version": "1.0x",
  "rights_basis": "Own gameplay capture; Rockstar video policy",
  "monetization_permission": "unconfirmed",   // or "not-monetized" / "take-two-written-permission"
  "third_party_audio": "none",                // after checking radio/music was off
  "voice": "my own commentary"
},
"shots": [
  {"type": "play",   "in": 120.0, "out": 126.5, "zoom": [1.0, 1.15]},
  {"type": "freeze", "at": 126.4, "dur": 0.8, "label": "WAIT FOR IT..."},
  {"type": "play",   "in": 126.5, "out": 133.0, "fx": ["shake"]},
  {"type": "replay", "in": 129.0, "out": 131.0, "speed": 0.5, "transition": "fade"},
  {"type": "play",   "in": 133.0, "out": 138.0, "framing": "fill", "focus": [0.6, 0.5]}
],
"captions": [ {"src": [120.2, 122.0], "text": "it started with one bump"} ],
"texts":    [ {"t0": 0, "t1": 2.4, "style": "hook", "text": "It started with [ONE] bump…"} ]
```
- Shot types: `play`, `freeze` (hold a frame with a Ken Burns zoom), `replay` (default 0.5x, highlight border + flash).
- `framing`: `blur` (gameplay panel over a blurred background, default), `fill` (9:16 crop at `focus`), `fit` (whole 16:9 frame), `native` (already 9:16, e.g. a SupoClip export).
- `fx`: `flash`, `shake`, `highlight`, `glitch`, `bw`, `vignette`. `audio`: `keep`, `duck`, `mute` (use `mute` for radio).
- `transition` (on the incoming shot): `cut` (default) or any ffmpeg xfade name (`fade`, `slideup`, `zoomin`, `circleopen`, ...).
- Captions: `src` = source time (mapped through the edit). For exact word sync, add `"words": [{"w": "it", "s": 120.21, "e": 120.35}, ...]`
  from SupoClip's transcript (AssemblyAI/Whisper word timestamps). `[brackets]` highlight words in hooks/cards/thumbnails.
- Text styles: `hook` (top, first 1-2 s), `label`, `card` (fact cards), `caption`.
- `sfx`: `[{"t": 3.2, "name": "hit"}]` (`whoosh hit pop riser ding glitch rewind tick`). Transitions, freezes, replays and the outro get SFX automatically.
4. `python -m studio render NN`, then `python -m studio qa NN`, then watch `final.mp4`.

## Using SupoClip itself (AI selection + gaming layout)
- Run SupoClip (`docker-compose up -d`, see the repo README), upload a capture, and enable
  `GAMING_LAYOUT=auto` for gameplay framing. SupoClip picks segments with AI scoring.
- **Clip count / batches:** SupoClip's count scales at roughly 1 clip per 5 minutes of source and is capped by `MAX_CLIPS`
  (default 10; `FAST_MODE_MAX_CLIPS` 10). To get 15, run several tasks (one per capture session, e.g.
  Group A sessions and a separate Group B session) instead of raising limits. Each task's best clips
  go into the manifests.
- Feed a SupoClip export into Shorts Studio with `"framing": "native"` to apply the channel's branding,
  captions style, rights gate, QA and paperwork.
- SupoClip's licence (Noncommercial Source License v1.1) allows monetized use by individual creators;
  companies, agencies and client work need written permission from its author.

## Rebranding
Edit `config/channel.json` (name, handle, colours, fonts from `backend/fonts`, watermark position/opacity)
and run `python -m studio brand`, then re-render.

## Files
`studio/branding.py` brand kit · `studio/sfx.py` synthesized SFX · `studio/render.py` edit/encode ·
`studio/captions.py` ASS captions · `studio/rights.py` permission gate · `studio/qa.py` QA ·
`studio/scan.py` highlight finder · `studio/docs.py` metadata/licence/audit/report · `manifests/` the 15 clips.
