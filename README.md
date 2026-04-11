# Spelix

**Science-grounded AI coaching for barbell lifts.** Upload a squat, bench, or deadlift video; get computer-vision form analysis and citation-grounded coaching feedback, streamed live.

Live at **[spelix.app](https://spelix.app)** · Built by [Atharva Kulkarni](https://linkedin.com/in/athkulk) ([@atharva6905](https://github.com/atharva6905))

<!-- TODO: add a 15-30s demo GIF here once recorded. Capture: upload → streaming coaching appearing → 4-dim score cards. Commit as docs/demo.gif and reference:
![Spelix demo](docs/demo.gif)
-->

---

## Why this exists

Every AI form-checking app on the market has the same two problems: **it can't tell you why**, and **it doesn't know when it's wrong**.

App Store reviews of the current leader complain about the same thing — identical clips produce "vastly different answers". A [2024 JMIR study](https://www.jmir.org/) evaluated AI-generated exercise recommendations across 26 clinical populations and found only **8%** cited any source, with overall comprehensiveness scoring **41.2%** against ACSM gold-standard guidelines. No product combines:

1. **Computer vision form analysis** — most either don't have it or don't commit to it.
2. **RAG grounding in peer-reviewed literature** — everyone hand-waves the "science-backed" claim.
3. **Expert validation workflow** — real kinesiology review, not just an LLM.

Spelix is a greenfield build by a solo student developer to fill that gap for squat, bench press, and deadlift — the three lifts that dominate strength training and have the richest biomechanics literature. Phase 1 shipped in April 2026. Phase 2 (the RAG + citations layer) is in progress.

---

## What it does

You upload a video. Spelix runs this pipeline end-to-end in ~60 seconds:

1. **Pose extraction** — MediaPipe BlazePose Heavy extracts 33 body landmarks per frame.
2. **Rep detection** — exercise-specific state machines find rep boundaries and phases.
3. **Per-rep metrics** — joint angles, eccentric duration, lockout quality, phase of maximum deviation, bar path (OpenCV centroid tracking), rep-to-rep consistency.
4. **Keyframe vision** — GPT-4o analyzes frames at depth / lockout / phase-of-max-deviation.
5. **Confidence scoring** — 5-tier confidence model (landmark → angle → frame → phase-adjusted → per-rep 10th percentile) decides what's trustworthy.
6. **Form scoring** — 4-dimension composite: Movement Quality (safety), Technique, Path & Balance, Control (eccentric tempo + rep consistency). Each 1.0-10.0, weighted into an Overall Form Rating.
7. **Coaching** — Claude Sonnet 4.6 generates coaching feedback over Server-Sent Events, with prompt caching. Phase 2 adds citation grounding over a peer-reviewed biomechanics corpus.
8. **Report** — results page with annotated video, per-rep table, bar path chart, streaming coaching, and a downloadable PDF with keyframe captures + citations.

---

## Architecture

<!-- TODO: commit an Excalidraw or Mermaid export as docs/architecture.png and embed:
![Architecture diagram](docs/architecture.png)
-->

```
Browser (React 19 + Vite 8 + TS + Tailwind + shadcn)
    │
    │  HTTPS REST + SSE
    ▼
FastAPI (Python 3.12)  ──→  Supabase Auth / Storage / Realtime / Postgres
    │                            ▲
    │  enqueue                   │ status push
    ▼                            │
ARQ async worker  ───────────────┘
    │
    ├─→ MediaPipe BlazePose Heavy (33 landmarks)
    ├─→ OpenCV (bar path tracking)
    ├─→ GPT-4o (keyframe vision)
    ├─→ Claude Sonnet 4.6 (coaching, SSE + prompt caching)
    ├─→ [Phase 2] Cohere embed-v4 + BM25 + Cohere Rerank 3.5
    ├─→ [Phase 2] Qdrant Cloud (vector store)
    ├─→ [Phase 2] CoVe verification + RAGAS faithfulness gate
    └─→ WeasyPrint (PDF report generation)
```

**Infra**: FastAPI + ARQ on a DigitalOcean 2 GB droplet behind Caddy (auto TLS). Frontend on Vercel. Supabase for Postgres + Storage + Auth + Realtime. Qdrant Cloud for vectors (Phase 2+).

---

## The hard parts (for curious engineers)

Highlights of the non-obvious decisions — long-form write-ups in [`docs/decisions.md`](./decisions.md).

**5-tier confidence model.** A naïve "is this frame usable?" is a lie. Spelix composes confidence at five levels: per-landmark (presence × detection sigmoid), per-angle (min of 3 contributing landmarks, because one bad joint poisons the angle), per-frame (weighted by which landmarks matter for the current exercise), phase-adjusted (eccentric/concentric weighting), and per-rep (10th percentile across all frames in the rep, so a single mid-rep occlusion doesn't nuke confidence). The UI only shows coaching for reps above a confidence floor, and "Very Low" reps are suppressed entirely.

**Stream-then-reparse coaching.** The SRS said "stream the LLM response directly"; reality said "structured output + streaming don't compose cleanly in `instructor`'s current state." Phase 1 ships a stream-then-reparse pattern: stream the raw Claude response to the browser for latency, then re-validate through `instructor` for structure. Doubles token cost. The alternative — wait for the full structured response before streaming — cost the product's perceived responsiveness. This is [documented tech debt D-001](./backlog.md) with a concrete Phase 2 migration plan to `instructor`'s native streaming structured extraction. Shipping this way > not shipping.

**Movement Quality, not injury prevention.** The internal field is `form_score_safety`, the user-facing label is "Movement Quality". Enforced across backend prompts, frontend copy, PDF templates, and every error string. The rename is a legal/compliance decision: claiming "injury prevention" triggers FDA Software-as-a-Medical-Device classification and FTC substantiation rules requiring RCT-level evidence. "Movement Quality" is a wellness claim. Same analysis, different liability.

**Keyframe extraction at rep boundaries.** GPT-4o vision is expensive per token, so we don't send every frame. We extract 4-6 keyframes per rep at exercise-specific semantic moments (descent start, depth, lockout, phase of max deviation). This reduces vision spend ~20× vs. sliding-window sampling, while preserving the moments where form actually goes wrong.

**Exercise auto-detection with GPT-4o fallback.** A heuristic detector classifies the lift from pose kinematics. If confidence is below threshold (usually unusual camera angle or partial reps), the pipeline falls back to a single GPT-4o vision call on a sampled frame. Real-world videos don't come labeled.

**Production engineering discipline.** Phase 1 ships with 895 backend tests / **91% coverage**, 177 frontend tests, TDD-first development, Alembic migrations applied atomically per session, multi-stage Docker builds, GitHub Actions CI running `ruff` / `pyright` / `pip-audit` / `pytest` against a real Postgres (not mocks), Sentry integration, GDPR-safe structured JSON logging. This is the thing that separates "portfolio project" from "product."

---

## Stack

**Backend** — Python 3.12, FastAPI (lifespan-managed), SQLAlchemy 2.0, Alembic, Pydantic v2, ARQ (async Redis queue), APScheduler, slowapi rate limiting
**CV** — MediaPipe BlazePose Heavy, OpenCV headless, Savitzky-Golay smoothing, NumPy
**AI** — Anthropic Claude Sonnet 4.6 (coaching, prompt caching), OpenAI GPT-4o (keyframe vision + exercise detection fallback), Cohere embed-v4 + Rerank 3.5 (Phase 2+), Qdrant Cloud (Phase 2+)
**Frontend** — React 19, Vite 8 (Rolldown), TypeScript strict, Tailwind 4, shadcn/ui, Recharts, Supabase JS (`@supabase/ssr`)
**Database & storage** — Supabase (Postgres + Storage + Auth + Realtime), TUS resumable upload
**Infra** — DigitalOcean droplet, Docker Compose, Caddy (auto TLS), Vercel (frontend), GitHub Actions CI
**Observability (Phase 4)** — LangSmith, Langfuse, Datadog Pro, Sentry
**Reports** — WeasyPrint for PDF, matplotlib for bar path charts

---

## Status

| Phase | Focus | Status |
|-------|-------|:------:|
| **Phase 0** — Core platform | Auth, upload, CV pipeline, rep detection, profiles, results UI | ✅ Complete |
| **Phase 1** — Multimodal foundation | GPT-4o keyframes, Claude coaching (SSE + caching), 4-dim scoring, 5-tier confidence, PDF reports | ✅ Shipped April 2026 |
| **Phase 2** — RAG knowledge layer | Cohere hybrid retrieval, Qdrant, CoVe verification, RAGAS faithfulness gate, citation tooltips, follow-up chat | 🟡 In progress |
| **Phase 3** — Agent orchestration | LangGraph agent, composable tools, adaptive reasoning, agent trace UI | 🗓 Planned |
| **Phase 4** — Eval infrastructure | Golden dataset, deepeval metrics, Langfuse logging, expert review queue, admin eval dashboard | 🗓 Planned |

Phase 1 numbers: **895 backend tests / 91% coverage, 177 frontend tests, migration 003 applied.**

See [`backlog.md`](./backlog.md) for the full task history and [`docs/SRS.md`](./docs/SRS.md) for the authoritative requirements spec.

---

## Screenshots

<!-- TODO: capture 3-4 screenshots from spelix.app and commit as docs/screenshots/
     Suggested: (1) upload page with overlay, (2) results page with 4-dim score cards + bar path chart,
     (3) streaming coaching in-progress, (4) PDF report page with keyframe embeds. -->

*Coming soon — see [spelix.app](https://spelix.app) for the live product.*

---

## About this repo

This is a **public showcase repo** — a curated view of the spelix codebase kept in sync with the live product. It exists to document the interesting technical decisions, not to be a runnable distribution. The canonical product is at [spelix.app](https://spelix.app); source is not released under an open-source license.

<!-- TODO: if you decide to make the full repo public, delete the paragraph above and replace with a "Getting Started" / "Local Development" section. -->

**Want a demo account for spelix.app?** Reach out — [atharvakulkarni023@gmail.com](mailto:atharvakulkarni023@gmail.com) or [LinkedIn](https://linkedin.com/in/athkulk).

**Interested in the product?** There's a beta tester list — email to join. Feedback from real lifters is the thing that makes Spelix better.

---

## About the builder

I'm **Atharva Kulkarni**, a 3rd-year Software Engineering student at **McMaster University**, incoming AI/ML intern at **Saturniq.tech** (Summer 2026), and looking for **Fall 2026 AI/ML/SWE intern + co-op roles** (4-16 month terms) in Canada and the US.

If you're a hiring manager: Spelix is the work I'm most proud of. It's the intersection of computer vision, multimodal LLM engineering, RAG, production infra, and honest domain research — roughly the surface area of a Senior AI Engineer role, shipped from scratch as a student. I'd love to talk about what I'm building and what a good fit would look like.

- **Email**: [atharvakulkarni023@gmail.com](mailto:atharvakulkarni023@gmail.com)
- **LinkedIn**: [linkedin.com/in/athkulk](https://linkedin.com/in/athkulk)
- **GitHub**: [@atharva6905](https://github.com/atharva6905)

---

## Acknowledgements

Spelix is built in collaboration with a Year 3 Pre-Med kinesiology student who serves as expert reviewer — curating the RAG corpus, labeling the golden evaluation dataset, and validating angle thresholds against published research. The science-grounded positioning only works because the science is actually validated.

Built with [Claude Code](https://claude.com/claude-code), [Anthropic](https://anthropic.com), [OpenAI](https://openai.com), [Cohere](https://cohere.com), [Supabase](https://supabase.com), [Qdrant](https://qdrant.tech), and far too much coffee.
