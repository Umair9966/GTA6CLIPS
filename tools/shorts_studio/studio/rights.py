"""Copyright / permission gate. Nothing renders without passing BLOCKED checks, and
nothing is ever marked approved for publication automatically.

Statuses:
  BLOCKED   - may not be rendered (no footage, unknown rights, leaked/pre-release, isolated cutscene,
              third-party creator footage without written permission, unlicensed music)
  FLAGGED   - may be rendered for review, but NOT cleared for monetized publication
              (e.g. monetization permission unconfirmed, unverified facts, spoilers, game audio risk)
  READY_FOR_HUMAN_REVIEW - rights documented; still requires the owner's final manual sign-off
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

OK_MONETIZATION = {"take-two-written-permission", "not-monetized"}
YOUTUBE_HOSTS = ("youtube.com", "youtu.be", "twitch.tv", "kick.com", "tiktok.com")


def evaluate(m: Dict[str, Any]) -> Tuple[str, List[str], List[str]]:
    """Returns (status, blocking_reasons, flags)."""
    src = m.get("source", {})
    blocks: List[str] = []
    flags: List[str] = []
    path = (src.get("path") or "").strip()

    if not path:
        blocks.append("No source footage assigned yet (source.path is empty).")
    elif any(h in path.lower() for h in YOUTUBE_HOSTS) or path.lower().startswith("http"):
        blocks.append("Source is a URL. This pipeline never downloads third-party streams/videos; "
                      "supply your own local capture file.")
    elif not Path(path).is_file():
        blocks.append(f"Source file not found: {path}")

    if not (src.get("rights_basis") or "").strip():
        blocks.append("source.rights_basis is empty: ownership/permission of the footage is undocumented.")
    owner = (src.get("owner") or "").strip()
    if path and not owner:
        blocks.append("source.owner is empty.")
    if src.get("third_party_creator_footage"):
        if not (src.get("third_party_permission_doc") or "").strip():
            override = (src.get("owner_override") or "").strip()
            if override:
                # The channel owner explicitly instructed use of this footage without a permission
                # document. Render for review, but never clear it.
                flags.append("NOT CLEARED: footage, voice and likeness belong to another creator "
                             f"({src.get('owner') or 'unknown'}) and NO permission is on file. Rendered only "
                             f"on the channel owner's explicit instruction ({override}). Uploading risks "
                             "Content ID claims, copyright strikes and channel termination. Get written "
                             "permission before publishing.")
            else:
                blocks.append("Footage belongs to another creator and no written permission document is recorded.")
    if src.get("leaked_or_prerelease"):
        blocks.append("Leaked / pre-release footage is not allowed (Rockstar policy).")
    if src.get("isolated_cutscene"):
        blocks.append("Isolated cutscene footage is not allowed (Rockstar policy: cutscenes only within "
                      "a larger play-through/commentary).")

    music = m.get("music") or {}
    if music.get("path") and not (music.get("license") or "").strip():
        blocks.append("Background music has no documented license.")

    monet = (src.get("monetization_permission") or "unconfirmed").strip()
    if monet not in OK_MONETIZATION:
        flags.append("Monetization rights unconfirmed: Rockstar's video policy grants permission for "
                     "non-commercial use; ad-revenue use is not explicitly covered. Get written permission "
                     "from Take-Two (copyright@take2games.com) or publish without monetization.")
    tpa = (src.get("third_party_audio") or "").strip().lower()
    if tpa not in ("", "none"):
        flags.append(f"Third-party audio present ({src.get('third_party_audio')}): licensed radio music "
                     "can trigger Content ID claims. Record with in-game radio off or mute those sections.")
    elif path and not tpa:
        flags.append("source.third_party_audio not declared (state 'none' after checking radio/music is off).")
    if src.get("story_spoilers"):
        flags.append("Contains story spoilers: Rockstar's policy says spoiler videos may be removed; "
                     "add a clear spoiler warning or cut it.")
    for fact in m.get("facts", []):
        if not fact.get("verified"):
            flags.append(f"Fact not yet verified against an official source: \"{fact.get('claim')}\"")
    if m.get("style") == "glitch" and path and not m.get("glitch_reproduced_in_footage"):
        flags.append("Glitch must be visible in this footage (set glitch_reproduced_in_footage=true after checking).")

    if blocks:
        return "BLOCKED", blocks, flags
    if flags:
        return "FLAGGED", blocks, flags
    return "READY_FOR_HUMAN_REVIEW", blocks, flags
