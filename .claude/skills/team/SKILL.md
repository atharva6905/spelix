---
name: team
description: Spawn an Agent Team for cross-domain tasks where specialists need to negotiate with each other. Use when workers need to communicate mid-task — not just report results. For independent parallel tasks with no coordination needed, use /parallel or worktrees instead.
argument-hint: "scenario: phase1-multimodal | debug | review | phase2-rag | phase3-agent | custom"
---

# Agent Teams — Spelix

## The Decision Rule

**Use /team only when the answer to this question is YES:**
"Do the workers need to talk to each other to produce correct output?"

If no — use `/parallel` (subagents) or `claude --worktree name` (separate terminals).
Agent Teams consume ~3–4× more tokens than subagents. Only use them when the
cross-agent communication is what makes the output correct.

## Cost Rules (follow every time, no exceptions)

1. **Sonnet for all teammates** — never Opus for teammates, only for the team lead
2. **Maximum 3 teammates** for Spelix (cost + 2GB RAM constraint)
3. **Keep spawn prompts focused** — teammates load CLAUDE.md automatically; don't
   repeat what's already there. Spawn prompt = task + scope + success criteria only
4. **Shut the team down immediately when work is done** — idle teammates burn tokens
   - `Shift+Down` to reach each teammate → type "you're done, shut down"
   - Or tell the lead: "shut down all teammates now"

## Before Spawning — Check

```bash
# Verify agent teams are enabled
echo $CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS  # must print 1

# Verify you're on latest main
git fetch origin && git status
```

If the env var isn't set, add it to `.claude/settings.json` under `env` and restart CC.

---

## Pre-Built Team Configurations

### Scenario: `phase1-multimodal`

**When**: Phase 1 — building GPT-4o keyframe analysis + form scoring + SSE coaching simultaneously.
**Why teams**: spelix-cv-engineer and spelix-coaching-engineer must agree on the keyframe
data contract (what shape the CV pipeline hands to coaching). They cannot do this
independently — one will build the wrong interface.

**Spawn prompt to give the team lead:**
```
Create an Agent Team with 3 teammates for Phase 1 multimodal integration.
Use Sonnet for all teammates.

Teammate 1 (spelix-cv-engineer): Implement the keyframe extraction system —
extract frames at rep boundaries, annotate with landmark coordinates, and define
the KeyframePayload schema that coaching will consume. Files: backend/app/cv/keyframes.py,
backend/app/schemas/keyframe.py. Write failing test first.

Teammate 2 (spelix-coaching-engineer): Implement the Phase 1 coaching service —
receive KeyframePayload + rep_metrics, call GPT-4o for keyframe descriptions,
call Claude Sonnet for structured coaching output, stream via SSE.
Files: backend/app/services/coaching.py, backend/app/api/v1/coaching.py.
Coordinate with Teammate 1 on KeyframePayload schema before implementing.

Teammate 3 (spelix-tdd): Implement the Phase 1 results page upgrade — four
dimension score pills, Movement Quality warning at score < 3.0, SSE streaming hook.
Files: frontend/src/pages/ResultsPage.tsx, frontend/src/hooks/useCoachingStream.ts.
Wait for Teammate 2 to confirm the SSE event format before implementing the hook.

Teammates: coordinate via the shared task list. Teammates 1 and 2 must agree on
KeyframePayload before either commits. Require plan approval from me before any
teammate writes to alembic/ or modifies existing schema files.
```

---

### Scenario: `debug`

**When**: A bug has multiple plausible root causes. 3 iterations haven't converged.
Faster to test theories in parallel than sequentially.
**Why teams**: teammates compare findings with each other, eliminating theories faster.

**Spawn prompt pattern:**
```
Create an Agent Team with 2 teammates to investigate [bug description].
Use Sonnet for both teammates.

Teammate 1: Investigate hypothesis A — [specific theory]. Read [relevant files].
Reproduce the failure, prove or disprove the hypothesis, report findings to the team.

Teammate 2: Investigate hypothesis B — [specific theory]. Read [relevant files].
Reproduce the failure, prove or disprove the hypothesis, report findings to the team.

When both have findings, compare notes and agree on the root cause before either
attempts a fix. Report the agreed root cause to me.
```

---

### Scenario: `review`

**When**: Pre-merge review of a large change set. Two independent reviewers catch
more than one reviewing sequentially because they don't anchor on each other's findings.
**Why teams**: reviewers challenge each other's conclusions before reporting to lead.

**Spawn prompt pattern:**
```
Create an Agent Team with 2 reviewer teammates.
Use Sonnet for both.

Teammate 1 (spelix-auditor): Review [files/PR] for SRS compliance — check all Must
requirements for Phase [N], JSONB columns, status transitions, language violations.
Report CRITICAL/HIGH/MEDIUM findings.

Teammate 2 (spelix-security-reviewer): Review the same [files/PR] for security —
JWT validation, RLS policies, SaMD language, secret exposure, input validation.
Report CRITICAL/HIGH findings.

After both complete their reviews, compare findings and flag any conflicts or
overlapping issues. Present a unified report to me.
```

---

### Scenario: `phase2-rag`

**When**: Phase 2 — building the RAG ingestion pipeline, hybrid retrieval, and corpus
validation simultaneously.
**Why teams**: the ingestion pipeline and retrieval system must agree on the Qdrant
payload schema (what metadata fields are stored and how they're structured for filtering).

**Spawn prompt pattern:**
```
Create an Agent Team with 3 teammates for Phase 2 RAG build.
Use Sonnet for all teammates.

Teammate 1 (spelix-rag-engineer): Build the PDF ingestion pipeline —
unstructured.io parsing → Cohere embed-v4 → Qdrant upsert. Define the QdrantPayload
schema including all metadata fields. Files: backend/app/services/ingestion.py.

Teammate 2 (spelix-rag-engineer): Build hybrid retrieval — dense + BM25, filtered
by exercise_type, Cohere Rerank 3.5. Must use the same QdrantPayload schema as
Teammate 1. Coordinate schema before implementing. Files: backend/app/services/retrieval.py.

Teammate 3 (spelix-corpus-curator): Audit the pending_review queue as ingestion runs —
verify metadata completeness, quality_tier values, exercise_types tags.
Read-only. Report gaps to the team task list.

Teammates 1 and 2: agree on QdrantPayload schema before either writes to Qdrant.
```

---

### Scenario: `phase3-agent`

**When**: Phase 3 — building LangGraph graph, typed AgentState, tool nodes, CoVe loop.
**Why teams**: the AgentState TypedDict is the shared contract. All teammates must
agree on it before building their respective nodes.

**Spawn prompt pattern:**
```
Create an Agent Team with 3 teammates for Phase 3 agent build.
Use Sonnet for all teammates.

Teammate 1 (spelix-langgraph-engineer): Design and implement the AgentState TypedDict
and LangGraph graph structure — node definitions, conditional edges, CoVe loop.
Files: backend/app/agent/graph.py, backend/app/agent/state.py.
Publish the AgentState schema to the team task list before any teammate implements tool nodes.

Teammate 2 (spelix-langgraph-engineer): Implement the 7 tool nodes once AgentState
is published — get_rep_metrics, get_keyframe_analysis, retrieve_knowledge,
generate_coaching_draft, generate_cove_questions, verify_cove_answers, revise_coaching.
Files: backend/app/agent/tools.py. Do not start until Teammate 1 publishes AgentState.

Teammate 3 (spelix-tdd): Write the LangGraph test suite — CoVe loop termination,
cove_verified flag, agent_trace structure, max iterations guard.
Files: tests/unit/test_langgraph_agent.py. Coordinate with Teammates 1 and 2 on
the expected state shape before writing assertions.

Require plan approval from me before any teammate modifies alembic/ or existing services/.
```

---

### Scenario: `custom`

**When**: none of the above match. Compose a team from scratch.

**Checklist before spawning:**
- [ ] Tasks require cross-agent communication (if not → use /parallel or worktrees)
- [ ] ≤ 3 teammates
- [ ] All teammates use Sonnet
- [ ] Spawn prompt is < 10 sentences per teammate
- [ ] CLAUDE.md content is NOT repeated in spawn prompt (it loads automatically)
- [ ] Plan approval required if any task touches alembic/ or existing models/schemas/

---

## Monitoring a Running Team

```
Shift+Down      # Cycle to next teammate
Shift+Up        # Cycle to previous teammate
                # (wraps back to lead after last teammate)
```

Type directly to message a specific teammate. The lead coordinates, but you can
intervene with any teammate directly without going through the lead.

Watch for: a teammate claiming tasks it shouldn't own, two teammates editing the
same file (conflict risk), or a teammate idling without claiming a new task.

## Shutting Down

After all teammates report done:
1. Tell the lead: "Review all teammate outputs, merge their branches, shut down the team"
2. Lead merges, runs `/check` + `/test`, then shuts down teammates
3. Main session continues for any follow-up

Alternatively, if the lead has already shut down: `Shift+Down` to each remaining
teammate → "your work is done, you can shut down now"

Do NOT leave teammates running while idle. Each idle teammate continues consuming tokens.