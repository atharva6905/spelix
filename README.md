# Spelix

**Science-grounded AI coaching for barbell lifts.** Upload a squat, bench, or deadlift video; get computer-vision form analysis and citation-grounded coaching feedback, streamed live, retrieved from a peer-reviewed corpus and a compounding knowledge layer that learns from every analysis.

Live at **[spelix.app](https://spelix.app)** · Solo-engineered by [Atharva Kulkarni](https://linkedin.com/in/athkulk) ([@atharva6905](https://github.com/atharva6905)), with domain-expert collaboration on the science — 3rd-year Software Engineering @ McMaster, looking for Fall 2026 AI/ML/SWE intern + co-op roles in Canada and the US.

<!-- demo.gif: 15-30s upload → streaming coaching → 4-dim score cards. Drop into docs/ then reference: ![Spelix demo](docs/demo.gif) -->

---

## Why this exists

Every AI form-checking app on the market has the same two problems: **it can't tell you why**, and **it doesn't know when it's wrong**. App Store reviews of the current category leader complain that identical clips produce "vastly different answers". A [2024 JMIR Medical Education study](https://mededu.jmir.org/2024/1/e51308) evaluating AI-generated exercise recommendations across 26 clinical populations found overall comprehensiveness scored **41.2%** against ACSM gold-standard guidelines, with citation to primary literature one of the consistently weakest categories.

The closest CV-based competitor (AiKYNETIX) ships pose tracking but no peer-reviewed grounding and no expert validation; "AI form coach" apps generally pick one of the three pillars below. No published product combines all three:

1. **Computer-vision form analysis** with a calibrated, per-rep confidence model.
2. **RAG retrieval grounded in peer-reviewed biomechanics literature**, curated by a domain expert through a role-gated reviewer portal.
3. **A compounding knowledge layer** that distills validated insights from real coaching outputs, gated by Chain-of-Verification against the research corpus before human review.

Spelix is a greenfield build to fill that gap for squat, bench press, and deadlift — the three lifts that dominate strength training and have the richest biomechanics literature.

---

## What it does

You upload a video. Spelix runs the pipeline end-to-end in roughly **4-5 minutes** — pose extraction, quality gates, rep detection, per-rep metrics, keyframe vision, confidence scoring, agentic retrieval, CoVe-verified coaching, and async distillation — and **streams coaching to the browser as soon as scoring completes**, well before the full structured response is validated. The user sees partial advice while the rest of the pipeline finishes.

1. **Pose extraction** — MediaPipe BlazePose Heavy extracts 33 body landmarks per frame.
2. **Quality gates** — anchor-based identity-jump detection rejects clips where MediaPipe re-acquires onto bystanders; visibility-gated bbox check enforces framing without false rejections from low-visibility hallucinations.
3. **Rep detection** — exercise-specific state machines find rep boundaries and phases, with a peak/valley fallback for partial-lockout edge cases.
4. **Per-rep metrics** — joint angles, eccentric duration, lockout quality, phase of maximum deviation, OpenCV bar-path centroid tracking, rep-to-rep consistency.
5. **Keyframe vision** — GPT-4o analyzes 4-6 keyframes per rep at exercise-specific semantic moments (descent start, depth, lockout, phase of max deviation).
6. **Confidence scoring** — 5-tier confidence model (landmark → angle → frame → phase-adjusted → per-rep 10th percentile) decides what's trustworthy. Reps below the floor are suppressed.
7. **Form scoring** — 4-dimension composite: Movement Quality, Technique, Path & Balance, Control. Each 1.0-10.0, weighted into an Overall Form Rating. Threshold config is versioned in-repo with PR review as the approval flow.
8. **Agentic retrieval + coaching** — a LangGraph agent with six composable tools (`get_rep_metrics`, `retrieve_papers`, `retrieve_coach_brain`, `flag_form_deviation`, `compare_to_user_history`, `generate_correction_plan`) selects retrieval strategy by docstring, queries a dual-collection Qdrant store (peer-reviewed papers + Coach Brain), and Claude Sonnet 4.6 streams citation-grounded coaching over SSE with prompt caching.
9. **Async distillation** — every completed analysis feeds a 7-node distillation StateGraph (`extract_insights → validate_quality → lifecycle_decision → cove_verify → format_entry → store_entry`, plus an idle terminal). Chain-of-Verification is run against the research corpus; cosine-threshold lifecycle decides ADD / UPDATE / NOOP / TOMBSTONE; an admin review queue gates promotion to production retrieval.
10. **Report** — annotated MP4, per-rep table, bar-path chart, streaming coaching with inline citation tooltips, downloadable WeasyPrint PDF.

---

## Architecture

<!-- docs/architecture.png — Excalidraw or Mermaid export of the diagram below -->

```
Browser (React 19 + Vite 8 + TS strict + Tailwind 4 + shadcn/ui)
    │
    │  HTTPS REST + Server-Sent Events
    ▼
FastAPI (Python 3.12, async)  ──────→  Supabase (Auth / Storage / Realtime / Postgres + RLS)
    │                                          ▲
    │  enqueue                                 │ status push
    ▼                                          │
streaq async worker  ──────────────────────────┘
    │
    ├─→ MediaPipe BlazePose Heavy (33 landmarks, Tasks API)
    ├─→ OpenCV headless (bar-path tracking)
    ├─→ GPT-4o (keyframe vision + exercise auto-detect fallback)
    ├─→ LangGraph agent (composable tools, adaptive selection, LangSmith-traced)
    ├─→ Cohere embed-v4 + BM25 + Cohere Rerank 4.0-pro (hybrid retrieval)
    ├─→ Qdrant Cloud (dual collection: papers_rag + coach_brain)
    ├─→ Claude Sonnet 4.6 (coaching, SSE + prompt caching, instructor-validated)
    ├─→ Distillation StateGraph (CoVe-verified, lifecycle-aware, human-gated promotion)
    └─→ WeasyPrint (PDF report generation)
```

**Infra:** FastAPI + streaq on a DigitalOcean 4 GB droplet behind Caddy (auto TLS). Frontend on Vercel. Supabase for Postgres + Storage + Auth + Realtime. Qdrant Cloud for vectors. GitHub Actions CI auto-deploys on merge to `main`.

**Observability:** LangSmith on every agent run; Langfuse for retrieval + RAGAS scoring; Sentry for application errors; structured JSON logs.

---

## The hard parts (for curious engineers)

Long-form write-ups in [`decisions.md`](./decisions.md). The summaries below cover the decisions that took the most thought.

### LangGraph agent with adaptive tool selection

The naive "single Claude call with all retrieved context" approach has two problems: it overpays for tokens on irrelevant retrieval, and it can't reason about whether to query Coach Brain at all. Spelix runs a typed `AgentState` blackboard through a LangGraph `StateGraph` with six composable tools. Tool selection is **docstring-driven** — Claude reads each tool's docstring and picks based on the analysis state, rather than following a fixed script. The graph supports both deterministic flow (production default) and adaptive mode (behind an env flag for ablation comparisons). Every run is LangSmith-traced; the trace is rendered back to the user as a "How AI Reasoned" sidebar via `@xyflow/react`.

**Shipped on 2026-04-15 (Phase 3 Batch 1). LangSmith-traced on every production run; the agent trace is rendered back to the user as a "How AI Reasoned" sidebar.**

### Coach Brain — a compounding knowledge layer with CoVe-verified distillation

Phase 2 RAG over papers is commodity. The defensible piece is what happens **after** coaching ships: every completed analysis flows through an async distillation StateGraph that extracts candidate insights, validates them against an eval gate (`overall ≥ 0.85 AND correctness ≥ 0.8`), runs Chain-of-Verification ([Dhuliawala et al., ACL 2024](https://arxiv.org/abs/2309.11495)) against the peer-reviewed corpus, and routes via cosine similarity to the existing Coach Brain:

- cosine `> 0.92` → NOOP (already known).
- `0.75 ≤ cosine ≤ 0.92` → UPDATE (bump `confirmation_count` on the existing entry; `cosine == 0.92` confirms, not skips, per FR-BRAIN-17).
- cosine `< 0.75` → ADD candidate to the admin review queue.
- `contradiction_flag = true` → tombstone the contradicted entry (`status='deprecated'` + `extra_metadata.rejected_reason` JSONB pointer to the contradicting candidate).

A domain expert reviews ADD candidates with a four-dimension eval scorecard, the CoVe verification result, the nearest existing entry's confirmation count, and approve / reject / edit / skip keyboard shortcuts. Only approved candidates join the production `coach_brain` collection and shape future retrieval.

**End-to-end proven 2026-04-17: a single bench analysis produced 11 candidates correctly routed through ADD / UPDATE / NOOP / tombstone with CoVe verification against `papers_rag` and an admin review-queue UI shipped behind the same gate.**

### 5-tier per-rep confidence

A naive "is this frame usable?" is a lie. Spelix composes confidence at five levels: per-landmark (`sigmoid(visibility) × sigmoid(presence)`), per-angle (`min` of three contributing landmarks — one bad joint poisons the angle), per-frame (weighted by which landmarks matter for the current exercise), phase-adjusted (eccentric/concentric weighting; lower weights for known-occluded phases), and **per-rep as the 10th percentile** of phase-adjusted frame confidences across the rep. The 10th percentile is pessimistic by design — a single mid-rep occlusion drags confidence down, which matches user intuition. The UI suppresses coaching for reps below the floor.

**Result: reps with brief mid-rep occlusion correctly flag Low / Very-Low; the UI suppresses coaching for reps below the floor, so users never see structured advice on a frame the model couldn't see.**

### Eval discipline

Coaching that can't be measured can't be improved. Spelix runs RAGAS faithfulness on every analysis as a Phase 2 retrieval-time gate; per-analysis traces land in Langfuse with the prompt, retrieved chunks, and the faithfulness score, and every LangGraph agent run lands in LangSmith with full tool-call telemetry. Phase 4 is the natural next step: a 100-query golden dataset built from real private-beta analyses, multi-component RAGAS (faithfulness + answer_relevancy + context_precision), a deepeval correctness suite, and a CI gate that blocks merges below the faithfulness floor. Faithfulness target is **≥ 0.85** by July 2026.

**Today: faithfulness gate live in production; Langfuse + LangSmith traces on every analysis. Tomorrow: golden dataset + multi-component RAGAS + deepeval correctness in CI.**

### Anchor-based quality gates for commercial-gym videos

The first naive `check_single_person` rejected real videos with bystanders by treating MediaPipe's tracker re-acquisition during occlusion as "multiple people" — an unactionable error message ("please film alone"). The first naive `check_framing` built its bounding box from all 33 raw landmarks, so MediaPipe-hallucinated low-visibility landmarks clustered at the body center shrank the bbox and rejected portrait framing. Both shipped, both broke private beta on real fixtures.

The fix: identify a lifter anchor from the first three high-visibility samples; only reject `check_single_person` on sustained ≥4 consecutive or >30% off-anchor samples. Filter the framing bbox to landmarks with `sigmoid(visibility) ≥ 0.5`. Calibrate the framing floor empirically against three production fixtures (squat / bench / deadlift, all 1080×1920 portrait at 60 fps, all commercial-gym shoots) until all three pass without false acceptances on synthetic negatives. Total wall-clock from bug surface to prod E2E green: ~6 hours, two PRs, one calibration follow-up.

**All three production fixtures (squat / bench / deadlift, commercial-gym shoots with 3-6 bystanders visible) now pass on prod end-to-end. Two PRs + one calibration follow-up; private beta launch unblocked.**

### Stream-then-reparse coaching (acknowledged tech debt)

The SRS said "stream the LLM response directly"; reality said `instructor`'s structured-output streaming was unreliable when this was written. Phase 1 shipped a stream-then-reparse pattern: stream Claude's raw text to the browser via Redis pub/sub for perceived latency, then re-validate through `instructor` for structure. This costs roughly 2× the single-call token budget. The alternative — wait for the full structured response before streaming — would have killed perceived responsiveness. Tracked as ADR-021 / D-001 with a concrete migration path to `instructor.create_partial` once the upstream API stabilizes.

**Result: users see partial coaching streaming into the browser well before the structured response is validated, while the final `CoachingOutput` Pydantic object always conforms to schema for downstream consumers (PDF, history, follow-up chat).**

### "Movement Quality", not "injury prevention"

The internal field is `form_score_safety`, the user-facing label is "Movement Quality". This isn't a defensive hedge — it's the truthful claim. Spelix measures how well a movement matches biomechanical optima; it does not claim to predict injury, because the literature does not support a per-clip injury prediction. The naming, enforced across backend prompts, frontend copy, PDF templates, and every error string, also keeps Spelix outside FDA Software-as-a-Medical-Device classification (which would require RCT-level evidence) and outside the FTC's substantiation rules for "injury prevention" claims. Same analysis, principled framing, different liability surface.

**Enforced across the backend prompt corpus, frontend copy, PDF templates, and error strings; every user-facing PR is gated by a SaMD-language reviewer subagent.**

---

## Stack

- **Backend** — Python 3.12, FastAPI (lifespan-managed), SQLAlchemy 2.0 async, Alembic, Pydantic v2, **streaq 6.4.0** (anyio structured concurrency, replaced ARQ), APScheduler, slowapi.
- **Computer vision** — MediaPipe BlazePose Heavy (Tasks API), OpenCV headless, Savitzky-Golay smoothing, NumPy.
- **AI** — Anthropic Claude Sonnet 4.6 (coaching, prompt caching, `instructor`-validated), Claude Haiku 4.5 (Chain-of-Verification), OpenAI GPT-4o (keyframe vision + exercise detection fallback), Cohere embed-v4 + Rerank 4.0-pro, **LangGraph + LangSmith** (agent + tracing), Langfuse.
- **Frontend** — React 19, Vite 8 (Rolldown), TypeScript strict, Tailwind 4, shadcn/ui, Recharts, `@xyflow/react` (reasoning sidebar), Supabase JS (`@supabase/ssr`).
- **Database & storage** — Supabase (Postgres + Storage + Auth + Realtime + RLS), TUS resumable upload, Qdrant Cloud (dual collection, 1024-dim, BM25 sparse, payload indexes).
- **Infra** — DigitalOcean droplet (Docker Compose, Caddy auto-TLS), Vercel for frontend, GitHub Actions CI auto-deploys on merge to `main`.
- **Reports** — WeasyPrint PDF, matplotlib for bar-path charts.

---

## Status

| Phase | Focus | Status |
|-------|-------|:------:|
| **Phase 0** — Core platform | Auth, upload, CV pipeline, rep detection, profiles, results UI | ✅ Complete |
| **Phase 1** — Multimodal foundation | GPT-4o keyframes, Claude coaching (SSE + caching), 4-dim scoring, 5-tier confidence, PDF reports | ✅ Complete |
| **Phase 2** — RAG knowledge layer | Cohere hybrid retrieval, Qdrant dual collection, CoVe verification, RAGAS faithfulness gate, citation tooltips, follow-up chat, expert reviewer portal | ✅ Complete |
| **Phase 3** — Agentic orchestration | LangGraph agent with composable tools, adaptive reasoning, distillation StateGraph, knowledge lifecycle, admin review queue, reasoning sidebar | ✅ Complete (2026-04-27) |
| **Phase 4** — Eval infrastructure | Multi-component RAGAS, 100-query golden dataset, Langfuse-driven eval dashboard, LangSmith ablation harness | 🗓 Planned |

**Numbers:** ~1908 backend tests / 91% coverage, ~364 frontend tests, Alembic head at migration 022. CI runs `ruff` / `pyright` / `pip-audit` / `pytest` against a real Postgres (not mocks) on every PR. See [`backlog.md`](./backlog.md) for the full task history and [`docs/SRS.md`](./docs/SRS.md) for the authoritative requirements spec.

**Up next:** rolling private-beta invites (May 2026), a five-post technical series on the decisions above — *Tier-5 Confidence*, *Stream-then-Reparse*, *Compounding Knowledge Layers*, *RAG + CV + Expert-in-the-Loop*, *RAGAS on Real User Data* — and Phase 4 eval infrastructure.

---

## Screenshots

<!-- Capture 4 from spelix.app post-redesign and commit to docs/screenshots/:
     1. Upload page with overlay
     2. Results page with 4-dim score cards + bar path chart
     3. Streaming coaching mid-flight with citation tooltips
     4. PDF report page with keyframe embeds
-->

*See [spelix.app](https://spelix.app) for the live product.*

---

## About this repo

This is a **public showcase repo** — a curated view of the Spelix codebase kept in sync with the live product. It exists to document the interesting technical decisions, not to be a runnable distribution. The canonical product is at [spelix.app](https://spelix.app); the source is not released under an open-source license.

**Read-only collaborator access to the private repo is available on request for hiring managers and recruiters** — email or LinkedIn (below). Access is revoked after the interview cycle.

---

## About the builder

I'm **Atharva Kulkarni**, a 3rd-year Software Engineering student at **McMaster University**, incoming AI/ML intern at **Saturniq.tech** (Summer 2026), looking for **Fall 2026 AI/ML/SWE intern + co-op roles** (4-16 month terms) in Canada and the US.

If you're hiring at **Anthropic, OpenAI, Cohere, DeepMind, Meta FAIR, Google Research, xAI, Scale, RBC Borealis, Shopify AI, Huawei Noah's Ark**, or any team building applied AI products at the intersection of CV / RAG / agent orchestration / production infra: Spelix is the work I'm most proud of. It's roughly the surface area of a Senior AI Engineer role, shipped from scratch as a student. I'd love to talk about what I'm building and what a good fit would look like.

- **Email** — [atharvakulkarni023@gmail.com](mailto:atharvakulkarni023@gmail.com)
- **LinkedIn** — [linkedin.com/in/athkulk](https://linkedin.com/in/athkulk)
- **GitHub** — [@atharva6905](https://github.com/atharva6905)

---

## Acknowledgements

Spelix is built in collaboration with a Year 3 Pre-Med kinesiology student who serves as the expert reviewer — curating the RAG corpus, labeling the golden evaluation dataset, validating angle thresholds against published research, and reviewing every Coach Brain candidate before promotion. The science-grounded positioning only works because the science is actually validated.

Built with [Claude Code](https://claude.com/claude-code), [Anthropic](https://anthropic.com), [OpenAI](https://openai.com), [Cohere](https://cohere.com), [Supabase](https://supabase.com), [Qdrant](https://qdrant.tech), and far too much coffee.
