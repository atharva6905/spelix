---
name: escalate
description: Write a structured escalation report to .claude/escalation.md when a bug has resisted 3 fix iterations. Formats the report for pasting into Claude.ai for external diagnosis. Run this instead of continuing to guess.
argument-hint: "brief description of what's failing"
---

# Bug Escalation Report

Run this command when:
- A bug has resisted 3 fix iterations
- The error involves an external service (Supabase, ARQ, Caddy) you cannot fully test locally
- You suspect the issue is architectural rather than a code bug

Do NOT escalate:
- After 1 or 2 attempts — try harder first
- For issues where the error message directly points to the cause
- For missing imports, type errors, or syntax issues

---

## What to Write

Create or overwrite `.claude/escalation.md`:

```markdown
# Escalation Report — [component name]
**Date**: [today]
**Task**: [backlog task ID]
**Attempts**: 3

## Failing test
```
[test name]
[exact error output — verbatim, no paraphrasing]
```

## Relevant code
**File**: [filename]
**Function**: [function name]
```python
[paste the relevant 10-30 lines of the actual function]
```

## What was tried

### Attempt 1
Hypothesis: [what I thought was wrong]
Change made: [what I changed]
Result: [new error or same error]

### Attempt 2
Hypothesis: [what I thought was wrong]
Change made: [what I changed]
Result: [new error or same error]

### Attempt 3
Hypothesis: [what I thought was wrong]
Change made: [what I changed]
Result: [new error or same error]

## Current hypothesis
[My best current theory about what's actually wrong]

## Environment context
Python version: [from `python --version`]
Relevant recent changes: [any recent migration, config change, or dependency bump]
Docker state: [running/stopped]
```

---

## After Writing the Report

1. Commit current state (even if broken) so the context isn't lost:
   ```bash
   git add -A
   git commit -m "wip(scope): escalation — [bug description]"
   ```

2. Update `.claude/handoff.md`:
   ```
   status: escalated
   blockers: [bug description — escalation.md written]
   next_action: "Await diagnosis from Claude.ai — paste .claude/escalation.md content"
   ```

3. Stop working on this bug. Do not attempt a 4th fix.

4. The human will paste escalation.md to Claude.ai, receive a diagnosis, and bring
   back a specific fix hypothesis. Implement that hypothesis as Attempt 4.

---

## Escalation Is Not Failure

A structured 3-attempt → escalate loop is faster than unlimited guessing.
The escalation report is also a record: if this bug recurs, the diagnosis is documented.
If the fix works, add the root cause to CLAUDE.md Gotchas immediately.
