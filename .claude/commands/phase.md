---
name: phase
description: Run the phase transition gate checklist before beginning a new phase. Verifies all Must requirements for the current phase are implemented, test coverage meets threshold, no CRITICAL audit findings remain, and CLAUDE.md is updated for the new phase. Requires human sign-off before proceeding.
argument-hint: "target phase number, e.g. 1"
---

# Phase Transition Gate

Run this command before the first task of a new phase.
The gate must pass before any Phase N implementation begins.

---

## Step 1: Verify Current Phase Is Complete

Run the full test suite and capture results:
```bash
cd backend && uv run pytest --cov=app --cov-report=term-missing
cd frontend && npx vitest run --coverage
```

Report:
- Backend test count and coverage %
- Frontend test count and coverage %
- Any failing tests (must be zero before proceeding)

---

## Step 2: Run spelix-auditor

Invoke the spelix-auditor agent for a full compliance pass:
```
Use the spelix-auditor agent to audit the current codebase against all Phase [N-1]
Must requirements. Report CRITICAL and HIGH findings.
```

Gate: **zero CRITICAL findings** before proceeding.
HIGH findings must be documented in backlog.md as fix tasks for early Phase N+1.
MEDIUM findings are acceptable carry-forward.

---

## Step 3: Verify Architecture Against SRS

Check each Must requirement for Phase N-1 in SRS.md Section 3.
For each requirement marked Must for Phase [N-1], verify it has:
- At least one passing test that directly tests the requirement
- Implementation in the correct file per CLAUDE.md architecture

List any Must requirement with no direct test → these are gaps that block the gate.

---

## Step 4: Update CLAUDE.md for New Phase

Update the following sections of CLAUDE.md for Phase [N]:

**Phase line** (near top):
```
**Current phase: Phase [N]** ([phase name])
```

**AI section** — update if Phase N introduces new LLM capabilities:
```
**AI (Phase [N])**: [updated capabilities, model, new patterns]
```

**Architecture Decisions** — add any new decisions from the phase just completed.

**Compaction Survival** — update:
```
After compaction: re-read @docs/SRS.md Section 3 for Phase [N] requirements.
Phase [N] complete when: [Phase N completion criteria from SRS]
```

---

## Step 5: Activate Phase N Specialist Agents

If Phase N introduces new specialist agents (per the Agent Roster in agents-strategy.md):

Check that their files exist in `.claude/agents/`:
- Phase 1: spelix-cv-engineer.md, spelix-coaching-engineer.md
- Phase 2: spelix-rag-engineer.md, spelix-corpus-curator.md
- Phase 3: spelix-langgraph-engineer.md
- Phase 4: spelix-eval-engineer.md

If any are missing, the agent files are in the project's agent design output.
Create them in `.claude/agents/` before proceeding.

---

## Step 6: Update handoff

```
phase: [N]
task: [first task ID for Phase N — open as a GitHub Issue]
status: ready
last_modified: [files changed in final Phase N-1 session]
failing_tests: []
blockers: []
next_action: "Begin Phase [N] — run /plan on [first task ID]"
session_count: [increment]
last_session: [today]
```

---

## Step 7: Human Sign-Off

Output a transition summary for review:

```
PHASE [N-1] → PHASE [N] TRANSITION SUMMARY

Test counts: Backend [X] tests, [Y]% coverage | Frontend [Z] tests
CRITICAL audit findings: [0 or list]
Unimplemented Must requirements: [none or list]
New agents activated: [list]
CLAUDE.md updated: [yes/no]

READY TO BEGIN PHASE [N]: [YES / NO — with reason if NO]

First task: [B-XXX] — [title]
Paste the Phase [N] Brief from PROMPT_TEMPLATES.md to confirm and begin.
```

**Wait for confirmation before starting any Phase N implementation.**
The human will paste a Phase Kickoff Brief (Template 1 from PROMPT_TEMPLATES.md).
That brief is the start signal.
