# Spelix Agent Architecture Strategy

## The Core Problem with the Current Workflow

Your `/parallel` skill is a **dispatch manual** — every time you run it, the main agent
reads the skill, constructs a massive context-heavy prompt, and sends each sub-agent
everything they need to know from scratch. The sub-agent starts cold. It has no knowledge
of MediaPipe's sigmoid quirk, Supabase's FK rules, or which words are banned from
user-facing strings. You paste it all in via the prompt string, every session.

`.claude/agents/` changes this architecture entirely.

---

## What `.claude/agents/` Actually Is

A file in `.claude/agents/spelix-cv-engineer.md` is a **persistent, named specialist**
with its own:

- **System prompt** — deep domain expertise baked in permanently
- **Tool list** — enforced at the kernel level, not via prompt instructions
- **Model** — e.g., Haiku for read-only audits, Sonnet for implementation
- **Permission mode** — `plan` mode for safe preview before execution
- **Isolation** — `isolation: worktree` makes every dispatch automatically isolated
- **Memory** — optional persistent memory directory across sessions

The main agent auto-delegates when it recognises a matching task, or you can invoke
explicitly: `"Use the spelix-cv-engineer agent to implement FR-CVPL-07"`.

The parent receives only the final output. All the intermediate file reads, search
results, and tool calls stay inside the agent's context — they never touch your main
conversation window. This is the feature that prevents context exhaustion on your
long sessions.

**Critical constraint**: subagents cannot spawn other subagents. The main agent is
always the orchestrator. The `/parallel` command remains the right tool for orchestrating
multi-agent batches — but instead of feeding generic workers a 40-line context dump,
it now routes tasks to named specialists who already know the codebase.

---

## The New Orchestration Model

```
Main Agent (orchestrator)
├── reads backlog.md
├── runs pre-flight checklist (from /parallel skill)
├── dispatches to named agents:
│   ├── "Implement B-093 → spelix-cv-engineer"       (knows MediaPipe, scoring)
│   ├── "Implement B-084 → spelix-tdd"               (knows test structure)
│   └── "Implement B-083 → spelix-tdd"               (frontend, knows vitest)
└── on completion: runs /check + /test, updates backlog.md

vs. before:
Main Agent (orchestrator)
├── reads backlog.md
├── constructs 40-line context dump per agent
├── dispatches to 3 identical generic workers
└── on completion: same
```

The parent prompt shrinks from a wall of context to a two-line delegation call.
The specialist agent already knows everything about its domain.

---

## Agent Roster — Phase by Phase

### Tier 0: Always Active (all phases)

| Agent | Model | Tools | When |
|-------|-------|-------|------|
| `spelix-tdd` | Sonnet | Read, Write, Edit, Bash, Glob, Grep | Any feature or fix task — TDD gate enforced |
| `spelix-auditor` | Haiku | Read, Grep, Glob (read-only) | SRS compliance checks, gap analysis, audit passes |
| `spelix-security-reviewer` | Sonnet | Read, Grep, Glob (read-only) | Pre-commit: any change touching auth, user strings, or user data |
| `spelix-migration` | Sonnet | Read, Write, Edit, Bash | Any Alembic migration or schema change |

### Tier 1: Phase 1 (add when starting Phase 1)

| Agent | Model | Tools | When |
|-------|-------|-------|------|
| `spelix-cv-engineer` | Sonnet | Read, Write, Edit, Bash, Glob, Grep | Any task in `backend/app/cv/` — MediaPipe, scoring, quality gates |
| `spelix-coaching-engineer` | Sonnet | Read, Write, Edit, Bash | Coaching service, SSE streaming, LLM prompt work, instructor schemas |

### Tier 2: Phase 2 (add when starting Phase 2)

| Agent | Model | Tools | When |
|-------|-------|-------|------|
| `spelix-rag-engineer` | Sonnet | Read, Write, Edit, Bash | Qdrant, Cohere embed/rerank, hybrid retrieval, ingestion pipeline |
| `spelix-corpus-curator` | Haiku | Read, Grep, Glob (read-only) | Corpus quality audits, metadata completeness checks |

### Tier 3: Phase 3 (add when starting Phase 3)

| Agent | Model | Tools | When |
|-------|-------|-------|------|
| `spelix-langgraph-engineer` | Sonnet | Read, Write, Edit, Bash | LangGraph graph, AgentState, CoVe loop, LangSmith tracing |

### Tier 4: Phase 4 (add when starting Phase 4)

| Agent | Model | Tools | When |
|-------|-------|-------|------|
| `spelix-eval-engineer` | Sonnet | Read, Write, Edit, Bash | deepeval metrics, Langfuse logging, CI regression, golden dataset |

**Rule on roster size**: the docs warn that too many agents degrades auto-delegation
accuracy. Keep to ≤6 active at any time. Tier 0 agents are always 4. Add Tier 1 agents
when Phase 1 begins and they become the dominant workload. Agent files can exist in
`.claude/agents/` before their phase begins — they won't be invoked until tasks
matching their description appear.

---

## How to Update `/parallel` for the New Model

The updated `/parallel` skill's Agent Prompt Template should shrink significantly.
Instead of a 15-line context dump, each dispatch call becomes:

```
Use the spelix-cv-engineer agent to:
TASK: B-093 — implement lighting + stability warning gates
SRS: FR-CVPL-08, FR-CVPL-09
FILES: backend/app/cv/quality_gates.py, tests/unit/test_quality_gates.py
TDD GATE: test_lighting_gate_rejects_dark_frame, test_stability_gate_rejects_shaky_video
```

The agent already knows: Python import rules, run_in_executor pattern, pytest structure,
ruff/pyright constraints, commit conventions, worktree isolation rules, and every
MediaPipe gotcha. None of that needs to be in the dispatch call.

---

## Ambitious Workflows — Phase-Specific Ideas

### Phase 1: The Multimodal Analysis Pipeline

When Phase 1 begins (GPT-4o keyframe analysis + form scoring), the heaviest work is in
`cv/` and `services/coaching.py`. These are independent enough to parallelize with
specialist agents:

```
Dispatch for Phase 1 Batch:
  spelix-cv-engineer  → FR-SCOR-01–04 (4 scoring dimensions)
  spelix-coaching-engineer → FR-COACH-01–05 (structured output + SSE streaming)
  spelix-tdd → FR-RESL-01 (results page Phase 1 upgrade)
```

The CV engineer already knows the ScoreComponent composite pattern, ThresholdConfig
loading, and which column semantics change between Phase 0 and Phase 1. The coaching
engineer already knows the instructor schema, the "never say injury" rule, and the SSE
hook pattern.

### Phase 2: Autonomous RAG Corpus Ingestion

The corpus ingestion pipeline (FR-RAGK-02 through FR-RAGK-07) involves distinct layers
that can be built in parallel with true specialist knowledge:

```
Dispatch for Phase 2 Corpus Build:
  spelix-rag-engineer → PDF ingestion pipeline (unstructured.io → Cohere → Qdrant)
  spelix-rag-engineer → Hybrid retrieval + Cohere Rerank 3.5 integration
  spelix-corpus-curator → Audit pending_review queue metadata completeness
```

The `spelix-corpus-curator` is read-only by tool restriction — it physically cannot
modify the Qdrant index, only report on what it finds. This is a safety property you
cannot get from a prompt instruction alone.

### Phase 3: LangGraph Agent as Self-Contained Work

Phase 3 is the biggest single-phase build: LangGraph graph, typed AgentState, 7 tool
nodes, CoVe verification loop, LangSmith tracing, agent trace UI. The `spelix-langgraph-engineer`
agent carries the full Blackboard pattern context, CoVe spec (draft → verify → revise),
the 7 tools from the class diagram, and LangSmith instrumentation patterns. A single
delegation call like "implement the CoVe verification loop per SRS Section 3.17" will
produce correct output without re-explaining the architecture.

### Phase 4: Autonomous Eval Regression

The eval infrastructure (deepeval + Langfuse) is a perfect headless-mode candidate.
Once `spelix-eval-engineer` exists:

```bash
claude -p "Run the eval regression suite against the current coaching output. 
Report faithfulness, groundedness, and contextual recall deltas vs baseline." \
--allowedTools "Read,Bash" \
--agent spelix-eval-engineer
```

This runs overnight unattended. The eval engineer knows the RAGAS thresholds
(faithfulness ≥0.8, groundedness ≥0.8), the golden dataset structure, and how to
read Langfuse logs.

---

## Implementation Order

1. **Now**: create the 4 Tier 0 agents — use them immediately for B-071–B-093
2. **Before Phase 1 starts**: create `spelix-cv-engineer` and `spelix-coaching-engineer`
3. **Before Phase 2 starts**: create `spelix-rag-engineer` and `spelix-corpus-curator`
4. **Before Phase 3 starts**: create `spelix-langgraph-engineer`
5. **Before Phase 4 starts**: create `spelix-eval-engineer`

Each agent file is in this deliverable. Tier 0 agents are fully written.
Tier 1–4 agents include complete system prompts with phase-specific knowledge
so they're ready to drop in when the phase begins.
