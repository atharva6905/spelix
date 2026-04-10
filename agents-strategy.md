# Agent Roster — Spelix

Reference for phase transitions (Template 1) and retrospectives (Template 5).
Claude.ai reads this to know which agents to activate per phase and which to patch after poor performance.

---

## Roster — Phase by Phase

### Tier 0: Always Active (all phases)

| Agent | Model | Tools | Trigger |
|-------|-------|-------|---------|
| `spelix-tdd` | Sonnet | Read, Write, Edit, Bash, Glob, Grep | Any feature or fix task requiring TDD |
| `spelix-auditor` | Haiku | Read, Grep, Glob (read-only) | SRS compliance checks, audit passes, gap analysis |
| `spelix-security-reviewer` | Sonnet | Read, Grep, Glob (read-only) | Any commit touching auth, user data, or user-facing strings |
| `spelix-migration` | Sonnet | Read, Write, Edit, Bash | Any Alembic migration or schema change |

### Tier 1: Activate at Phase 1

| Agent | Model | Tools | Trigger |
|-------|-------|-------|---------|
| `spelix-cv-engineer` | Sonnet | Read, Write, Edit, Bash, Glob, Grep | Any task in `backend/app/cv/` — MediaPipe, scoring, quality gates |
| `spelix-coaching-engineer` | Sonnet | Read, Write, Edit, Bash | Coaching service, SSE streaming, LLM prompts, instructor schemas |

### Tier 2: Activate at Phase 2

| Agent | Model | Tools | Trigger |
|-------|-------|---------|---------|
| `spelix-rag-engineer` | Sonnet | Read, Write, Edit, Bash | Qdrant, Cohere embed/rerank, hybrid retrieval, ingestion pipeline |
| `spelix-corpus-curator` | Haiku | Read, Grep, Glob (read-only) | Corpus quality audits, metadata completeness, pending_review queue |

### Tier 3: Activate at Phase 3

| Agent | Model | Tools | Trigger |
|-------|-------|-------|---------|
| `spelix-langgraph-engineer` | Sonnet | Read, Write, Edit, Bash | LangGraph graph, AgentState, CoVe loop, LangSmith tracing |

### Tier 4: Activate at Phase 4

| Agent | Model | Tools | Trigger |
|-------|-------|-------|---------|
| `spelix-eval-engineer` | Sonnet | Read, Write, Edit, Bash | deepeval metrics, Langfuse logging, CI regression, golden dataset |

**Roster size rule**: keep ≤6 active agents at any time. Too many degrades auto-delegation accuracy.
Tier 0 = always 4. Add Tier N agents when Phase N begins and they become the dominant workload.
Agent files can exist in `.claude/agents/` before their phase — they won't trigger until matching tasks appear.

---

## Dispatch Pattern Per Phase

The correct parallelism pattern depends on whether agents need to coordinate with each other mid-task.

### Phase 0 (current) — MEDIUM backlog B-071–B-093
All tasks are independent. No cross-agent coordination needed.
→ **`/parallel`** for all batches, or **`claude --worktree name`** for 2–4 separate terminals.

### Phase 1 — Multimodal foundation
- **Multimodal integration batch** (cv-engineer + coaching-engineer + tdd): these agents must negotiate the KeyframePayload schema before either can implement. Use **`/team phase1-multimodal`**.
- **Independent tasks** (results page UI, test coverage, config): use **`/parallel`** or worktrees.

### Phase 2 — RAG knowledge layer
- **RAG build** (ingestion + retrieval + corpus audit): ingestion and retrieval must agree on the Qdrant payload schema. Use **`/team phase2-rag`**.
- **Independent tasks** (PubMed ingestion scripts, admin corpus UI): use **`/parallel`** or worktrees.

### Phase 3 — Agent orchestration
- **LangGraph build** (graph + tools + test coverage): all three must agree on AgentState TypedDict before implementing. Use **`/team phase3-agent`**.
- **Independent tasks** (agent trace UI, LangSmith setup): use **`/parallel`** or worktrees.

### Phase 4 — Eval infrastructure
- All eval tasks are independent (deepeval, Langfuse, dashboard are separate systems).
- Use **`/parallel`** or worktrees for implementation.
- Eval regression suite: use **headless mode** overnight (`claude -p "..."` with spelix-eval-engineer).

---

## When Template 5 Identifies an Agent Issue

If a specialist agent repeatedly produced wrong output during a phase, Claude.ai will
produce a system prompt patch in the Template 5 output. Atharva applies the patch by
editing the relevant file in `.claude/agents/` in the spelix repo.

The patch is specific text to add, change, or remove — not a full rewrite.
Each agent enters the next phase smarter than it left the previous one.
