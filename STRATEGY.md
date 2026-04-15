# Spelix Strategy — Fall 2026 Top-AI-Lab Internship Plan

**Created:** 2026-04-11 | **Rewritten:** 2026-04-14 (compressed timeline) | **Status:** ACTIVE | **Hard gate:** 2026-05-03 (Phase 3 + landing + expert wiring live on prod) | **Applications open:** mid-May 2026 | **Interviews:** July 2026

---

## Mission

Every decision in this document exists to land a **Fall 2026 summer internship at a top AI lab**: Anthropic, OpenAI, Cohere, DeepMind, Meta FAIR, Google Research, xAI, Inflection, Character, Scale, Adept-tier labs, or Canadian bigtech with a strong AI research arm (Shopify AI, Cohere-Canada, RBC Borealis, Huawei Noah's Ark). Every product milestone, public artifact, and hour of build time below is justified because it moves the needle on that application — nothing else.

Spelix is the **interview narrative vehicle**. It is a real product with real users because fake products convert at zero, but paid GTM, general-audience growth, and commercial strategy are explicitly off-table for 2026.

---

## External Calendar — Why The Timeline Is Compressed

- **Applications begin mid-May 2026.** This is the self-set target with a generous buffer for delays; we aim to stick to it.
- **Interviews begin July 2026.** By July, we need 4-6 weeks of real beta-user experience to draw from in behavioural + technical interviews.
- **Product state at application time (mid-May):** Phase 3 live on prod. Landing + private beta open to invited users. 3-5 trusted test users already through the flow.
- **Product state at interview time (July):** 1-1.5 months of accumulated beta usage, real retention data, expert-reviewed corpus growing, Coach Brain distilled entries in production.

Working backwards, this forces a 19-day hard gate at **May 3** for the entire Phase 3 + landing + expert-portal-wiring + streaq migration stack.

---

## The Two Things That Must Be True By Interview Time (July 2026)

The bar for an AI-lab engineering/research internship has risen to the point where "I shipped a full-stack app" is a baseline, not a differentiator. Two specific things convert:

### 1. Deep technical depth with novel ideation

Spelix's signal: **Phase 3 — LangGraph agent orchestration with a CoVe-verified distillation pipeline and a knowledge-lifecycle-aware Coach Brain.** All of Phase 3 must be live on prod by May 3 so that (a) real beta-user analyses populate it during May-July, and (b) by interview time I can speak to production behaviour, not a demo.

Components shipped by May 3:
- Typed `AgentState` Blackboard with composable tools: `get_rep_metrics`, `retrieve_papers`, `retrieve_coach_brain`, `flag_form_deviation`, `compare_to_user_history`, `generate_correction_plan`.
- Adaptive reasoning — LLM selects tools by docstring, not fixed script.
- LangSmith tracing on every agent run.
- Standalone distillation `StateGraph` — `extract_insights → validate_quality → format_entry → store_entry`. Eval gate: `overall ≥ 0.85 AND correctness ≥ 0.8`. Runs async; never blocks coaching.
- Knowledge lifecycle: cosine dedup thresholds (>0.92 NOOP, 0.75–0.92 UPDATE `confirmation_count`, <0.75 ADD candidate) + contradiction flagging.
- CoVe (Chain-of-Verification, Dhuliawala et al. ACL 2024) applied to every distilled candidate before the review queue.
- Coach Brain expert review queue in admin with eval scorecard + CoVe result + approve/reject/edit flow.
- "How AI Reasoned" sidebar on the Results page rendering the LangSmith trace via `@xyflow/react`.

### 2. Product uniqueness that survives a 5-minute interview challenge

Phase 2 RAG alone is commodity in 2026. The defensible moat is the **combination**: CV form analysis + expert-curated RAG corpus + compounding Coach Brain distillation + human-in-the-loop verification. No published product combines all four. That is the interview hook.

---

## Priorities (non-negotiable)

1. **Fall 2026 internship** — the sole priority.
2. **Spelix product shipping to the state that supports #1** — subordinate to (1), but cannot be skipped since it IS the portfolio artifact.

No third priority. No commercial branch. No fundraising. No mentions of any other summer commitment in this document.

---

## Level Progression (compressed)

| Level | Definition | Target Date |
|-------|-----------|-------------|
| **L1** | Live URL, polished landing placeholder, no real users | Done |
| **L2** | Phase 3 live + landing live + expert portal wired + streaq migration complete + 3-5 trusted test users through the flow | **2026-05-03** (hard gate) |
| **L3** | Private beta active, applications submitted, 10-20 real users, 1-2 blog posts public | **2026-05-15** |
| **L4** | 20-40 users, 4-6 weeks of retention data, expert-reviewed corpus ≥20 papers, 10+ distilled Coach Brain entries, 3 blog posts public, interview narrative bulletproof | **2026-07-01** (interviews begin) |
| **L5** | Applications submitted to 30-50 target companies, interviews completed, offer received | **2026-10-31** |

The old commercial/startup levels (L4 commercial, L5 startup) are removed from the strategic horizon.

---

## 19-Day Sprint Shape — Apr 14 to May 3

**Time budget:** full-time + (10-15 hrs/day). Feature work for Spelix dominates; interview prep is suspended until May 4 except for passive ambient reading.

**Parallelisation model:** solo lead + agent teams. `spelix-langgraph-engineer` activates on Day 10. `spelix-tdd` drives test-first component work. `spelix-migration` handles Alembic migration 008 (beta_requests) + any Phase 3 schema changes. Agent teams (`/team`) spawn where backend + frontend coordinate (e.g., reasoning sidebar + LangSmith API contract).

### Day 1-2 (Apr 14-15) — Landing V1 + Expert Portal Wiring

**Parallel track A (solo lead, or `spelix-tdd`):**
- Landing page V1 per `landing-page-plan.md`: Hero + Problem + How It Works + Three Differentiators + Privacy + CTA + email capture → manual approval.
- `public/beta-terms.md` drafted and rendered at `/beta-terms`.
- Alembic migration 008: `beta_requests` table, RLS, anonymous INSERT.
- PostHog instrumentation for landing events (`landing_view`, `landing_email_submit_*`).
- Merge via feature branch → CI → Playwright MCP E2E against live spelix.app.
- **Hard gate: landing live on prod by end of Day 2.**

**Parallel track B (agent team, `spelix-tdd` + `spelix-security-reviewer`):**
- **Expert Paper Upload — wire PDF upload end-to-end.** Current state: metadata-only form, no file input, no multipart handler. Needs:
  - Backend: add signed-URL endpoint (preferred, matches existing TUS pattern) OR accept `multipart/form-data` on `/api/v1/expert/papers` with `UploadFile`.
  - Frontend: add file input + progress UI to `ExpertPaperUploadPage.tsx`.
  - Security hardening: `Content-Type` + magic-byte check (must be real PDF), 50 MB size limit, filename sanitisation, Supabase Storage bucket RLS (expert_reviewer + admin write, service-role ingestion read).
  - Trigger Docling ingestion worker on successful upload.
  - `spelix-security-reviewer` audit before merge.
- **Hard gate: kin expert can successfully upload their first seed PDF end-to-end by end of Day 2.**

**Parallel track C (partnership):**
- Kin expert **onboarding call today** (60 min): walk the portal end-to-end, agree paper priority list, agree weekly/daily cadence, hand off log template → `docs/expert-cadence.md`.
- First 5 seed papers uploaded and approved end-to-end (paper upload should unblock on Day 2).

### Day 3-9 (Apr 16-22) — ARQ → streaq Migration

Per ADR-BRAIN-04, ARQ was in maintenance-only mode as of Feb 2026. streaq shipped v6.4.0 on April 10 2026 with anyio-based structured concurrency and self-reported 5× ARQ speed. Decision: **migrate now, compressed from the original 2-week budget to 7 days, scoped as drop-in replacement only** (no adoption of streaq's advanced features like task graphs or middleware during this window — those come post-L2 if ever).

**Scope:**
- Migrate the three critical job types: analysis pipeline (`run_analysis`), coaching stream worker, Qdrant keepalive cron (`ping_qdrant_health`).
- Expert paper ingestion (Docling) — migrate the ingestion job to streaq.
- Update `docker-compose.yml`, Dockerfile env, droplet deploy scripts.
- New ADR in `decisions.md` documenting the reversal of ADR-BRAIN-04's "defer to Phase 3" decision and the compressed scope.

**Kin expert ramp (parallel):**
- Phase B (steady throughput) kicks off in this window — target 5-10 papers reviewed by Day 9. Daily async touchpoints via GitHub issues or shared Google Doc.

### Day 10-16 (Apr 23-29) — Phase 3 Batches 1 + 2

**Activate:** `spelix-langgraph-engineer` (new agent).

**Batch 1 (Days 10-13, 4 days) — LangGraph Agent Core:**
- P3-001: `StateGraph` + typed `AgentState` + composable tools listed above. Conditional edges, deterministic flow first. SRS FR-AICP-18. (XL)
- P3-002: Adaptive reasoning — docstring-driven tool selection. SRS FR-AICP-19. (L)
- P3-003: LangSmith tracing integration. SRS FR-AICP-20. (M)

**Batch 2 (Days 13-16, 4 days, overlaps Batch 1 via Explore/Plan-first):**
- P3-004: Standalone distillation `StateGraph` (per ADR-BRAIN-07) — `extract_insights → validate_quality → format_entry → store_entry`. Eval gate `overall ≥ 0.85 AND correctness ≥ 0.8`. SRS FR-BRAIN-06. (XL)
- P3-005: Knowledge lifecycle ADD/UPDATE/NOOP with cosine thresholds + contradiction flagging. SRS FR-BRAIN-17. (L)
- FR-BRAIN-14 (Should): CoVe verification against `papers_rag` before every promotion.

**Kin expert (parallel):**
- Throughput target for this window: additional 5-10 papers, plus the first coaching-output annotations once Phase 3 agent is on prod with real analyses.

### Day 17-19 (Apr 30 - May 2) — Phase 3 Batch 3 + Smoke Test

**Batch 3 (Days 17-19, 3 days):**
- P3-006: Coach Brain expert review queue — single-screen cards with eval scorecard + CoVe result + approve/reject/edit, <30 sec/entry target, compensation entries flagged. SRS FR-ADMN-12, FR-BRAIN-07. (L)
- P3-007: "How AI Reasoned" sidebar on `ResultsPage` — `@xyflow/react` graph rendered from LangSmith trace, plain English per NFR-USAB-05. SRS FR-RESL-07. (M)

**Smoke test (Day 19, May 2 evening):**
- Invite 3-5 trusted test users (warm network only — McMaster barbell club, kinesiology partner's network). Each completes at least one upload → streaming coaching → results flow.
- Log bugs / UX issues to `docs/user-sessions/smoke-{date}-{initials}.md`.
- Fix CRITICAL bugs same-day; HIGH bugs into Day 20 buffer.

### Day 20 (May 3) — L2 Gate Audit

All gates below are required for L2-complete; any miss = triage before mid-May applications.

- [ ] Landing page V1 live on prod, email capture functional, migration 008 applied.
- [ ] Expert paper upload live on prod; kin expert has uploaded ≥5 papers end-to-end.
- [ ] ARQ → streaq migration complete; all three job types running on streaq.
- [ ] Phase 3 agent on prod, LangSmith traces visible.
- [ ] Distillation `StateGraph` operational (idle pending user data is OK).
- [ ] Coach Brain review queue accessible from admin panel.
- [ ] Reasoning sidebar renders on `ResultsPage` for at least one real test-user analysis.
- [ ] 3-5 trusted test users through the end-to-end flow.
- [ ] No CRITICAL production bugs open.

---

## Post-May-3 Plan — May 4 to July 1 (interview start)

### Sprint BETA — May 4 to May 14 (11 days)

**Theme:** roll out the private beta, ship application materials, publish blog posts, polish the frontend.

**Spelix work (~5-8 hrs/day; starting to decompress from the 10-15 hrs/day sprint pace):**
- Rolling invites from the beta-requests queue: approve in batches of 5, observe for UX issues, fix, invite next batch. Target by May 14: 15-20 approved beta users.
- **Full frontend visual redesign — bottom-priority, rolling delivery.** Landing was Day 1-2 of the May 3 sprint. Remaining pages (Upload, Status, Results, History, Profile, Admin, Expert portal) get redesigned piecemeal May 4-14. If a page doesn't land by May 14, it slips to after applications ship — acceptable.
- Blog posts 1-2 drafted and published (see Blog Plan below).
- User-session observations: 2-3 remote screen-shares with early beta users; write-ups to `docs/user-sessions/`.
- PostHog dashboard curated: retention D1/D3/D7, thumbs rate, coaching-view duration, Coach Brain retrieval contribution rate.

**Applications work (~3-4 hrs/day starting May 4):**
- Target-company list: 30-50 rows in `data/target-companies.md` — name, role(s), open date, visa support, referral path.
- CV v1 tailored for AI/ML intern roles.
- Cover letter templates: two variants (research-oriented + systems-oriented), A/B tested with 2 alumni if available.
- STAR+R story bank (5 stories, 150-200 words each) → `interview-prep/story-bank.md`.
- **Mid-May submission batch:** target 10 applications submitted by May 17 to companies with May open dates.

### Sprint GROW — May 15 to July 1 (6.5 weeks)

**Theme:** real user volume, expert throughput, eval numbers, blog posts, interview prep.

**Spelix work (~4-6 hrs/day):**
- Beta invites continue — target by July 1: 40-60 approved users, 20-30 weekly active.
- Weekly metrics review (Sundays, 30 min) → `docs/metrics/YYYY-Wxx.md`. Track: signups, retention, thumbs rate, Coach Brain contribution rate, RAGAS faithfulness on golden dataset.
- Expert throughput target: 20+ papers in `papers_rag`, 30+ coaching outputs annotated, 5+ Coach Brain candidates approved by July 1.
- Eval infrastructure: RAGAS (faithfulness, answer_relevancy, context_precision) on every completed analysis via Langfuse. Target: RAGAS faithfulness ≥ 0.85 on a 100+ query golden dataset.
- Blog posts 3-5 drafted and published (see Blog Plan below).
- Reddit post in r/weightroom (ONE attempt, read rules first, respect self-promo policy). Timing: late May once frontend is visually clean.

**Applications work (~4-6 hrs/day; ramps up through June):**
- Continue application submissions as listings open — target cumulative 30-40 by July 1.
- Alumni outreach: 2-3 LinkedIn DMs/week. Low volume, high signal, personalised each.
- LeetCode daily: 1 medium/day minimum.
- System design biweekly: Alex Xu vol 1/2.
- Fundamentals study 2 hrs/week: attention math, RLHF/DPO, KV cache, speculative decoding, MoE, diffusion, RAG eval metrics beyond RAGAS.
- Mock interviews monthly: technical / behavioural / system design rotation.

### Sprint INTERVIEW — July 1 onward

**Theme:** interviews active. Spelix on maintenance mode. Interview prep + referral pushes dominate.

- Bug fixes only on the product. No new features.
- Sunday 30-min metrics check. Alerts active so the product doesn't demand attention during interview prep.
- 5 alumni DMs/week pushing for referrals at companies with later-opening listings.
- LeetCode daily (1 medium + 1 hard every 2-3 days).
- Mock interviews weekly.
- System design biweekly.

---

## Kinesiology Expert Activation Plan

The expert reviewer portal shipped in Phase 2 (pages exist) but was discovered to have **no file-upload mechanism on the frontend and no multipart handler on the backend**. This is Day 1-2 work in the sprint above.

Once the portal works, the expert is available for **multiple weekly/daily touchpoints** — confirmed by the expert directly. The activation runs in parallel to every sprint below.

### Phase A — Onboarding (Day 1-2, Apr 14-15)
- **60-min onboarding call** (today, Apr 14) — walk the portal end-to-end once it is wired, agree paper priority list, agree weekly/daily cadence. Log cadence and priority journals to `docs/expert-cadence.md`.
- **Priority corpus** — agree 5 highest-value journals (J. Strength & Conditioning Research, J. Biomechanics, Sports Biomechanics, Medicine & Science in Sports & Exercise, International J. Sports Physiology & Performance) and 3-5 priority topics (squat biomechanics, bar-path efficiency, eccentric tempo, valgus and knee tracking, bench arch).
- **First deliverable:** 5 seed papers uploaded + approved end-to-end on Day 2 (unblocked by portal fix).

### Phase B — Steady Throughput (Apr 16 - May 3, during streaq + Phase 3 sprints)
- Target: **5-10 papers reviewed by Day 9 (Apr 22), another 5-10 by May 3.** Total by May 3: 10-20 papers in `papers_rag`.
- Daily or near-daily async touchpoints via GitHub issues or shared Google Doc.
- Weekly 30-min sync call to unblock ambiguities and align on the next week's priorities.
- Spot-check: I sample 10% of expert-approved papers for corpus-fit (on-topic? barbell relevant? high-quality methodology?). Misses discussed at the weekly sync.

### Phase C — Distillation + Coaching Annotation (May 4 - July 1)
- Once real user analyses are in production, split expert time: ~60% paper review, ~40% coaching-output annotation.
- Expert reviews Coach Brain distillation candidates through the FR-ADMN-12 queue as they accumulate.
- Target by July 1: **30+ papers approved, 30+ coaching outputs annotated with structured 1-10 quality scores, 5+ distilled Coach Brain entries promoted to the `coach_brain` collection.**

### Phase D — Interview-Period Maintenance (July 1 onward)
- Drops to 1 hr/week minimum-viable review. Paper corpus freeze allowed from July 1.
- Expert is credited in ONE_PAGER and landing page per SRS §829 verbatim:
  > *"AI coaching validated by a Kinesiology specialist (B.Sc. candidate). All coaching claims are grounded in peer-reviewed literature reviewed and curated by a qualified expert."*

### Interview-narrative outputs from expert activation
- **Paper count:** "30+ peer-reviewed papers curated by a kinesiology specialist, ingested into the RAG corpus via an expert-reviewer portal with role-gated PDF upload."
- **Annotation throughput:** "30+ coaching outputs reviewed by the domain expert with structured quality scores."
- **Distillation audit trail:** "Every Coach Brain entry in production was CoVe-verified against the research corpus and reviewed by an expert before promotion."
- **System design story:** "We built a role-gated expert portal with signed-URL PDF upload, magic-byte MIME validation, and a Supabase RLS policy isolating expert write access from service-role ingestion reads."

---

## Blog Plan

All posts live on `spelix.app/blog` (or dev.to as fallback). Each one is an interview conversation-starter and a public artifact that survives account deletion.

| # | Title | Target | Interview purpose |
|---|-------|--------|-------------------|
| 1 | *"Tier 5 Confidence: How Spelix Knows When It Doesn't Know"* | May 4-14 | Technical depth on the 5-tier per-rep confidence model (10th percentile of phase-adjusted frame confidences) |
| 2 | *"Stream-then-Reparse: The Trade-off Nobody Tells You About Instructor Streaming"* | May 4-14 | Pragmatic LLM infra story — SSE + partial JSON + schema re-parse on completion |
| 3 | *"Building a Compounding Knowledge Layer: CoVe + Cosine Dedup + Human Review"* | Jun 1-15 | The Coach Brain distillation architecture |
| 4 | *"RAG + CV + Expert-in-the-Loop: The Three-Layer Moat for Coaching AI"* | Jun 15 - Jul 1 | Synthesis piece — the one I link from every cold DM |
| 5 | *"Measuring RAG Quality on Real User Data: RAGAS Benchmarks from the Spelix Private Beta"* | Jun 20 - Jul 1 | Real numbers + methodology + limitations. Technical-depth signal. |

Post-May-3 target: **2-3 posts published by May 14** (to ship with mid-May applications). Remaining 2-3 posts published June-July before interviews begin.

---

## Interview Narrative Target

By 2026-07-01 I can say, verbatim, in a 90-second opening:

> *"Since April I've shipped Spelix — a barbell form coaching platform — to a private beta of 40+ real lifters. The system runs MediaPipe pose estimation through a tier-5 per-rep confidence model, then a LangGraph agent with composable tools retrieves from a dual-collection Qdrant vector store: one for peer-reviewed biomechanics literature curated by a kinesiology-specialist collaborator through an expert-reviewer portal, and one for a compounding knowledge layer called the Coach Brain. Coaching is streamed via SSE with inline citations. Every completed analysis feeds an async distillation StateGraph that applies Chain-of-Verification against the research corpus before human review; approved entries join the Coach Brain and shape future retrieval. I measure RAGAS faithfulness at 0.85+ on a 100-query golden dataset from real users, and the Coach Brain contributes to over 40% of production queries. The novelty is the system shape: no other published product combines CV pose, expert-curated RAG, and compounding distillation with human-in-the-loop verification."*

Every sentence maps to a concrete milestone. If a sentence cannot be truthfully said by July 1, the sprint owning it gets priority over any other Spelix work.

---

## North Star Metrics

| Level | Metric | Target |
|-------|--------|--------|
| L2 (May 3) | Landing page live on prod | ✓ |
| L2 (May 3) | Phase 3 agent + distillation live on prod | ✓ |
| L2 (May 3) | streaq migration complete | ✓ |
| L2 (May 3) | Expert portal PDF upload live + security-reviewed | ✓ |
| L2 (May 3) | Kin expert papers uploaded | 10+ |
| L2 (May 3) | Trusted test users through flow | 3-5 |
| L2 (May 3) | Critical bugs open | 0 |
| L3 (May 15) | Applications submitted | 10+ |
| L3 (May 15) | Beta users approved | 15-20 |
| L3 (May 15) | Blog posts published | 1-2 |
| L3 (May 15) | Pages redesigned | ≥ landing + 2 more |
| L4 (Jul 1) | Beta users total | 40-60 |
| L4 (Jul 1) | Weekly active users | 20-30 |
| L4 (Jul 1) | Expert-reviewed papers in `papers_rag` | 30+ |
| L4 (Jul 1) | Coach Brain entries in production | 5+ |
| L4 (Jul 1) | Coach Brain retrieval contribution rate | ≥ 30% |
| L4 (Jul 1) | RAGAS faithfulness on golden dataset | ≥ 0.85 |
| L4 (Jul 1) | Blog posts published | 4-5 |
| L4 (Jul 1) | Applications submitted | 30-40 |
| L5 (Oct 31) | Total applications submitted | 30-50 |
| L5 (Oct 31) | Interview conversion rate | > 20% |
| L5 (Oct 31) | Offer received | ≥ 1 |

---

## Privacy Policy (public surface area)

Source stays in the private repo. Public surface:

- **spelix.app** — live product, beta-gated behind manual email approval.
- **spelix-public repo** (future) — README, `docs/decisions.md`, SRS excerpts, architecture diagrams, `docs/ONE_PAGER.md`. Zero source code.
- **Blog posts** — technical deep-dives. Public writing beats public code as a technical-depth signal that survives an account deletion.
- **Loom walkthrough** — narrated codebase tour, unlisted YouTube / Loom link.
- **Recruiter code access** — read-only GitHub collaborator invite to the private repo, only when explicitly requested by a hiring manager. Revoked after the interview cycle.

Reason: fast-follower clone defense + genuine product uniqueness. Not paranoia — applied judgment about what gets shipped publicly vs privately.

---

## Stop-Loss Triggers

Revisit this strategy if any hit before 2026-10-31:

- A top-AI lab extends an offer outside this timeline (accept; freeze the plan).
- A paying customer appears unsolicited and cannot be deflected (reassess after the application cycle ends — do NOT pivot mid-cycle).
- Waitlist spikes past 1000 organically (good problem; triage with the runbook, do NOT launch a marketing response that steals from interview prep).
- **Phase 3 slips past May 3 by more than 3 days** — re-scope distillation pipeline (Batch 2 optional) or defer Batch 3 (review queue + reasoning sidebar) until post-L2. Agent core (Batch 1) is non-negotiable.
- **streaq migration blocks Phase 3 start by more than 5 days** — fall back to ARQ with `max_jobs=1`, `job_timeout=900` per ADR-BRAIN-04's original Phase-2 configuration. Migrate after interviews.
- **Expert portal security review surfaces a critical vulnerability that can't be fixed in Day 1-2** — delay kin expert onboarding, ship portal with expert_reviewer role check only (no uploads) until fixed.

---

## What This Document Is NOT

- Not a commercial GTM plan. L4 commercial and L5 startup are explicitly off the horizon for 2026.
- Not a fundraising strategy. No external capital is sought.
- Not a solo-founder manifesto. Spelix exists to land a job; it is the portfolio, not the destiny.
- Not a research paper. Publishable eval work is welcomed but not a primary deliverable.
- Not a public marketing plan. Every public artifact (blog posts, Loom, ONE_PAGER) exists because it converts interview applications, not because it drives acquisition.

---

## Required ADR Updates (log in `decisions.md` alongside first PR that reflects them)

- **ADR-BRAIN-04 reversal** — The original ADR deferred streaq migration to Phase 3 post-Saturniq. That decision is reversed: streaq migration happens within the May 3 sprint, compressed from 2 weeks to 7 days, scoped as drop-in replacement only. Justification: ARQ is in maintenance-only mode (GitHub #510, v0.27.0 Feb 2026); streaq v6.4.0 shipped April 10 2026 with anyio structured concurrency and 5× speed; being on an unmaintained queue weakens the interview narrative.
- **ADR-EXPERT-01 (new)** — Expert paper upload security model: signed-URL upload to Supabase Storage bucket with RLS (`expert_reviewer` + `admin` write, service-role ingestion read), `Content-Type` + magic-byte PDF validation, 50 MB size limit, filename sanitisation, Docling ingestion trigger on successful upload.
- **ADR-TIMELINE-01 (new)** — Phase 3 pulled forward from deferred post-Saturniq position to a compressed 19-day sprint ending 2026-05-03, driven by mid-May application deadline and July interview start.

---

## Change Log

- **2026-04-11** — Initial version. L2 sprint + summer-maintenance + post-summer application cycle.
- **2026-04-14 (v2)** — Full rewrite. Removed mentions of other summer commitments. Phase 3 pulled forward. Added Kin Expert Activation Plan.
- **2026-04-14 (v3, this version)** — Timeline compressed. External anchors locked to mid-May applications and July interviews. Phase 3 + landing + streaq + expert portal wiring all hit a hard May 3 gate. Expert portal PDF-upload wiring added as Day 1-2 blocker. streaq migration scope confirmed and compressed to 7 days after ARQ-vs-streaq research. Blog posts deferred to May 4-14 initial batch. Frontend redesign scoped as bottom-priority rolling delivery with landing as the only hard-gated page.
