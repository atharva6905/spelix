---
name: handoff
description: Write a structured handoff note before ending a session
---
Write a handoff file to .claude/handoff.md with these exact sections:
1. **Completed** — list each task ID with the commit SHA
2. **Remaining** — list each task ID from backlog.md that was not reached, with Deps status
3. **Test counts** — current `pytest` count and coverage %, and any known failures
4. **Blockers** — anything discovered that blocks the next session
5. **Next session start** — the exact first command to run

Overwrite any existing handoff.md. Do not commit it.