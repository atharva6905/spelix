---
name: adr
description: Capture an architecture decision record to decisions.md. Run whenever a non-trivial technical choice is made — library selection, pattern choice, API design decision, constraint adoption, or any decision that would be costly to reverse. This is the compounding memory of the project.
argument-hint: "decision title, e.g. 'use ARQ over Celery for async jobs'"
effort: low
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
- A pattern adopted to prevent a class of bug from recurring

Do NOT run /adr for:
- Implementation details that follow directly from an existing ADR
- Single-file style decisions
- Things already documented in CLAUDE.md
- Bug fixes that don't change architecture or constraints

---

## ADR Format

**File location**: `decisions.md` at the **repo root**, not `docs/decisions.md`.

Read `decisions.md` to find the next ADR number (current highest + 1). ADRs in this
project use a deliberately compact format — match it exactly so the file stays
greppable. Append using this template:

```markdown
## ADR-[NNN]: [decision title]
**Context**: [1-3 sentences explaining what situation forced this decision. Be specific —
reference the SRS section, the test failure, the bug, or the constraint that triggered it.]
**Decision**: [1-2 sentences naming the exact library, pattern, config value, or rule
that was adopted. Include the file paths or symbol names so future grep can find them.]
**Consequences**: [2-4 sentences explaining what becomes easier, what becomes constrained,
and any follow-on decisions or gotchas this creates for future work.]
```

**Title style**: specific and searchable. "Database decision" is bad. "No DDL FK constraint
to auth.users — enforce via RLS only" is good.

**Tone**: factual, technical, and self-contained. A reader 6 months from now should be
able to understand the decision without re-reading the SRS or the original PR.

**Length**: 4–10 lines per ADR. Compact > comprehensive. If you need more than 10 lines,
the decision is too broad — split it.

---

## After appending the ADR

ADRs are committed immediately as a small standalone docs commit:

```bash
git add decisions.md
git commit -m "docs(decisions): ADR-[NNN] [title]"
```

If the ADR is part of a larger code change in the same PR, you can either:
1. Bundle it into the PR commit (preferred for tightly-coupled code+ADR pairs)
2. Commit the ADR separately first (for standalone architectural decisions)

Either way, every ADR-worthy decision MUST land in `decisions.md` in the same PR
that introduces the decision — never in a follow-up cleanup PR. The whole point
is to make institutional memory atomic with the code.

---

## ADR Quality Check

Before committing, verify:
- [ ] The Context explains *why* this was a decision, not just what was decided
- [ ] The Decision names a specific symbol, file, or constant — not a vague pattern
- [ ] The Consequences include at least one constraint or gotcha for future work
- [ ] The title would be searchable 6 months from now without re-reading the body
- [ ] The format matches the existing 30+ ADRs in `decisions.md` exactly

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
