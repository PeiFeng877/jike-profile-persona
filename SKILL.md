---
name: jike-profile-persona
description: Fetch recent posts from a Jike/即刻 profile URL or username, handle QR login for web.okjike.com when needed, and generate either an evidence-backed personality portrait or a relationship-fit analysis based on the user's dating preferences. Use when the user provides an 即刻主页链接 and wants posts collected, summarized, profiled, or judged for compatibility.
version: 0.1.0
metadata:
  openclaw:
    requires:
      bins:
        - python3
---

# Jike Profile Persona

## Overview

Run the bundled script to collect up to 200 recent posts from a Jike profile, build a normalized corpus, and generate ready-to-analyze prompt packs.

The skill now supports two analysis modes:
- Base portrait: a vivid, evidence-backed public persona reading
- Compatibility advice: combine the user's dating preferences with the target's posts and give a friend-style suitability read

Treat both as text-based inference, not psychological diagnosis and not matchmaking science.

## Workflow

1. Normalize the input.
Accept:
- `https://m.okjike.com/users/<id>`
- `https://web.okjike.com/u/<username>`
- the raw Jike username/id itself

2. Pick an output directory.
Default to a task-local directory like `<cwd>/jike-profile-output` unless the user asked for a different location.

3. Run the fetch script.

```bash
python3 /Users/Icarus/.codex/skills/jike-profile-persona/scripts/jike_profile_persona.py "<profile-url-or-username>" --limit 200 --out-dir "<output-dir>"
```

If the user also gave their own ideal-partner preferences, expectations, turn-offs, or relationship concerns, pass them in one of these ways:

```bash
python3 /Users/Icarus/.codex/skills/jike-profile-persona/scripts/jike_profile_persona.py "<profile-url-or-username>" --limit 200 --out-dir "<output-dir>" --match-brief "<user-preferences>"
```

or

```bash
python3 /Users/Icarus/.codex/skills/jike-profile-persona/scripts/jike_profile_persona.py "<profile-url-or-username>" --limit 200 --out-dir "<output-dir>" --match-brief-file "<absolute-path-to-brief.md>"
```

4. Handle login when prompted.
If the script prints `Login required`, it will generate a QR image file in the output directory.
Show that file to the user as a local image in the app:

```markdown
![Jike login QR](/absolute/path/to/jike-login-qr.png)
```

Tell the user to scan it with the Jike app's built-in scanner. If they say the scan hangs, generate a fresh QR and tell them not to use the system camera or WeChat scanner.

5. Return the artifacts.
The script writes:
- `<username>.updates.json`
- `<username>.updates.corpus.md`
- `<username>.analysis-input.md`
- `<username>.match-analysis-input.md` when `--match-brief` or `--match-brief-file` is provided
- `jike-session.json` for cached refresh-token reuse
- `jike-login-qr.png` only when login is needed

6. Pick the right prompt-pack in-model.
Use:
- `<username>.analysis-input.md` for the base portrait
- `<username>.match-analysis-input.md` for the dating/compatibility scenario

Each prompt-pack already contains:
- the analysis voice and framing
- the profile metadata
- the normalized post corpus
- for the match scenario, the user's own preference brief

Do not fall back to the old regex/template style. The script is only responsible for collection and packaging.

7. Explain result limits clearly.
If the report contains fewer than 200 posts, say that the script fetched all currently available profile posts for that account. Do not imply the script stopped early unless there was an actual failure.

## Output Rules

- Prefer citing the generated corpus or prompt-pack instead of paraphrasing raw data from memory.
- Keep the explanation evidence-based. Quote or paraphrase specific posts and dates.
- State that the analysis is a content/persona inference, not a clinical or psychological diagnosis, and not a deterministic matchmaking verdict.
- If the user wants a tighter or different rubric, follow [analysis-rubric.md](references/analysis-rubric.md).
- If the user wants to change the voice or sharpness of the portrait, edit [persona-prompt.md](references/persona-prompt.md) rather than changing fetch logic.
- If the user wants a more playful or harsher compatibility read, edit [compatibility-prompt.md](references/compatibility-prompt.md).

## Notes

- The script uses authenticated web APIs after QR login.
- The current implementation fetches profile updates via the web profile stream and may return fewer than the requested count when the account itself has fewer public profile posts.
- Reuse `jike-session.json` when present; only re-authenticate when refresh fails.

## Resources

- `scripts/jike_profile_persona.py`: end-to-end fetch, login, corpus generation, and prompt-pack generation
- `references/analysis-rubric.md`: reporting rubric and guardrails
- `references/persona-prompt.md`: the main prompt template used for the final portrait
- `references/compatibility-prompt.md`: the friend-style prompt template for dating-fit advice
