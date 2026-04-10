---
name: adr
description: Capture an architecture decision record to decisions.md. Run whenever a non-trivial technical choice is made — library selection, pattern choice, API design decision, constraint adoption, or any decision that would be costly to reverse. This is the compounding memory of the project.
argument-hint: "decision title, e.g. 'use ARQ over Celery for async jobs'"
---

# Architecture Decision Record — Capture

Run this command whenever you make a non-trivial technical decision.
The test for "non-trivial": if someone asked "why did you do it this way?" in a code
review or interview, would the answer require more than one sentence? Then it's an ADR.

## When to run /adr

Run /adr for:
- Library or framework choices (why X over Y)
- Design pattern adoptions (Repository pattern, Composite pattern, Blackboard)
- Constraint decisions (max_jobs=1, no DDL FK to auth.users, 7-day artifact retention)
- Phase-transition decisions (what changes between Phase N and N+1)
- Decisions made to fix a bug that reveal a systemic design choice

Do NOT run /adr for:
- Implementation details that follow directly from an existing ADR
- Single-file style decisions
- Things already documented in CLAUDE.md

---

## ADR Format

Read `decisions.md` to find the next ADR number (current highest + 1).

Append to `decisions.md` using this format exactly:

```markdown
## ADR-[NNN]: [decision title]
**Date**: [today's date]
**Phase**: [current phase number]
**Status**: Accepted

**Context**
[1-3 sentences: what situation forced this decision. Be specific — reference
the SRS section, the test failure, or the constraint that triggered this.]

**Decision**
[1-2 sentences: what was decided. Be concrete — name the exact library, pattern,
config value, or rule that was adopted.]

**Options considered**
- Option A ([chosen]): [brief description + key benefit]
- Option B: [brief description + why rejected]
- Option C (if applicable): [brief description + why rejected]

**Consequences**
[2-4 bullet points: what this decision means for future work. Include:
 - what becomes easier
 - what becomes harder or constrained
 - any follow-on decisions this creates]

**SRS references**
[FR-IDs or NFR-IDs that relate to this decision, or "None"]
```

After appending:
1. Run: `git add docs/decisions.md`
2. Run: `git commit -m "docs: ADR-[NNN] [title]"`

ADRs are committed immediately — they are the project's institutional memory.

---

## ADR Quality Check

Before committing, verify:
- [ ] The context explains *why* this was a decision, not just what was decided
- [ ] At least 2 options are listed (including the chosen one)
- [ ] Consequences include at least one constraint on future work
- [ ] The decision title is specific enough to be searchable

A poor ADR title: "Database decision"
A good ADR title: "No DDL FK constraint to auth.users — enforce via RLS only"

---

## ADRs as Portfolio Evidence

Every ADR is a concrete story of technical judgment under constraint.
"I chose ARQ over Celery because it's async-native and avoids the Windows
multiprocessing issue we hit in the prototype — see ADR-002" is a better interview
answer than "we used ARQ."

The decisions.md file in this project is also uploaded to the Claude.ai project folder.
Keep both in sync at phase transitions.
