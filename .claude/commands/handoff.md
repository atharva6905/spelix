---
name: handoff
description: Write a structured handoff note before ending a session
---
Write a handoff file to .claude/handoff.md with these exact sections:
1. **Completed** — list each task ID with the commit SHA, plus the merged PR number for any checkpoint
2. **Remaining** — list each task ID from backlog.md that was not reached, with Deps status
3. **Test counts** — current `pytest` count and coverage %, and any known failures (backend + frontend)
4. **E2E verification** — for any user-facing feature merged this session, the Playwright MCP verification result against spelix.app: pass/fail, affected flows walked, any console errors or failed network requests observed. Skip this section for docs-only or CI-only sessions.
5. **Blockers** — anything discovered that blocks the next session
6. **Next session start** — the exact first command to run

Overwrite any existing handoff.md. Do not commit it.