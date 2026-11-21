# Master Report: GTA 6 Shorts

Generated 2026-11-21 02:28.

## Summary
- Clips planned: 15 (Group A: 9, Group B: 6)
- Rendered final.mp4: **15 / 15**
- Cleared for your final review: 0
- Published: 0 (this workflow never uploads)

## Source
- **04-15:** real GTA 6 gameplay from Creative Commons (CC BY) YouTube uploads, credited in each description.
- **01-03:** IShowSpeed stream clips: not licensed, already blocked by YouTube. **Do not upload.**
Format: 1080x1920, 30 fps, 2-3 minutes each (YouTube Shorts allow up to 3:00).

## Status
| # | Group | Style | Working title | Footage | Rights | QA |
|---|---|---|---|---|---|---|
| 01 | A | funny | IShowSpeed Needed a Car in GTA 6… So He Took One 😭 | yes | FLAGGED | BLOCKED |
| 02 | A | funny | IShowSpeed Felt SO Bad He Gave the Car Back 💀 (GTA 6) | yes | FLAGGED | FLAGGED_NOT_CLEARED_FOR_MONETIZED_PUBLICATION |
| 03 | A | funny | IShowSpeed Slapped an NPC by Accident in GTA 6 😭 | yes | FLAGGED | FLAGGED_NOT_CLEARED_FOR_MONETIZED_PUBLICATION |
| 04 | A | action | Stealing a TANK From the GTA 6 Military Base 💥 | yes | FLAGGED | FLAGGED_NOT_CLEARED_FOR_MONETIZED_PUBLICATION |
| 05 | A | action | Sneaking Onto the GTA 6 Cruise Ship… Then Stealing the Helicopter 🚁 | yes | FLAGGED | FLAGGED_NOT_CLEARED_FOR_MONETIZED_PUBLICATION |
| 06 | A | action | Robbing a Store in GTA 6… Then the Getaway 🏍️ | yes | FLAGGED | FLAGGED_NOT_CLEARED_FOR_MONETIZED_PUBLICATION |
| 07 | A | action | Living Like a Millionaire in GTA 6 Vice City 💰 | yes | FLAGGED | FLAGGED_NOT_CLEARED_FOR_MONETIZED_PUBLICATION |
| 08 | A | action | Taking a Porsche Through GTA 6 Vice City Traffic 🏎️ | yes | FLAGGED | FLAGGED_NOT_CLEARED_FOR_MONETIZED_PUBLICATION |
| 09 | A | action | Boat Ride Through the GTA 6 Keys 🌴 (This Water Is Unreal) | yes | FLAGGED | FLAGGED_NOT_CLEARED_FOR_MONETIZED_PUBLICATION |
| 10 | B | fact | What's Under the Water in GTA 6? 🌊 (You Can Actually Dive) | yes | FLAGGED | FLAGGED_NOT_CLEARED_FOR_MONETIZED_PUBLICATION |
| 11 | B | fact | GTA 6 Has HIKING? Mountains, Trails & Bikes 🏔️ | yes | FLAGGED | FLAGGED_NOT_CLEARED_FOR_MONETIZED_PUBLICATION |
| 12 | B | fact | Driving Across the ENTIRE GTA 6 Map (25 Minutes in 2:30) 🗺️ | yes | FLAGGED | FLAGGED_NOT_CLEARED_FOR_MONETIZED_PUBLICATION |
| 13 | B | fact | GTA 6 Graphics Are Unreal: The Best-Looking Shots 🤯 | yes | FLAGGED | FLAGGED_NOT_CLEARED_FOR_MONETIZED_PUBLICATION |
| 14 | B | fact | Tank, Heli, Porsche & More: GTA 6 Vehicles in Action 🚗🚁🚤 | yes | FLAGGED | FLAGGED_NOT_CLEARED_FOR_MONETIZED_PUBLICATION |
| 15 | B | fact | GTA 6 NPCs Are Way Too Real 😂 | yes | FLAGGED | FLAGGED_NOT_CLEARED_FOR_MONETIZED_PUBLICATION |

## Cross-clip repetition check
- No overlapping source ranges or duplicate frames detected among rendered clips.

## Pipeline self-test (synthetic test pattern, not a deliverable)
Result: **PASS**
  - resolution: PASS (1080x1920)
  - aspect_ratio: PASS (9:16, SAR 1:1)
  - frame_rate: PASS (60.00 fps)
  - codec: PASS (h264 yuv420p)
  - duration: PASS (27.30s (target 20-45s))
  - bitrate: PASS (8.3 Mbps)
  - audio_stream: PASS (aac 48000 Hz)
  - loudness: PASS (-14.3 LUFS integrated (target -14±2))
  - true_peak: PASS (-2.0 dBTP)
  - black_frames: PASS (0 black segment(s) [])
  - decode_errors: PASS (0 decoder messages [])
  - watermark: PASS (100% of watermark text pixels detected at expected position)
  - subtitle_timing: PASS (26 caption events, no overlaps, all in range)
  - subtitle_sync_source: FAIL (timing source: line timestamps (source time), words interpolated (interpolated word timing; spot-check by eye))
  - thumbnail: PASS (thumbnail.jpg)
  - metadata.txt: PASS (metadata.txt)
  - source_and_license_notes.txt: PASS (source_and_license_notes.txt)

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
