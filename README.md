# jike-profile-persona

Claw/Codex skill for:

- fetching up to 200 recent posts from a Jike/即刻 profile
- generating an evidence-backed personality portrait
- generating a friend-style relationship-fit analysis based on a user's dating preferences

## Files

- `SKILL.md`: skill instructions and metadata
- `scripts/jike_profile_persona.py`: login, fetch, corpus, and prompt-pack generation
- `references/persona-prompt.md`: base portrait prompt
- `references/compatibility-prompt.md`: dating-fit prompt

## Notes

- Requires `python3`
- Uses authenticated Jike web APIs after QR login
- ClawHub publish was attempted on 2026-03-23 but blocked by a ClawHub backend error, so this repo is the current distribution fallback
