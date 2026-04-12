# Data Protection Impact Assessment (DPIA)

**Spelix — Barbell Form Coaching Platform**

| Field | Value |
|-------|-------|
| Assessment date | 2026-04-12 |
| Controller | Spelix (spelix.app) |
| DPO recommendation | Appointment recommended before public launch |
| Legal basis | GDPR Article 9(2)(a) — explicit consent |
| Assessment trigger | GDPR Article 35(3)(a): systematic and extensive evaluation of personal aspects based on automated processing, including profiling, on which decisions are based that produce legal effects or similarly significant effects |
| SRS reference | FR-BRAIN-15, NFR-PRIV-06 |

---

## 1. Systematic Description of Processing Operations

*GDPR Article 35(7)(a)*

### 1.1 Purpose of Processing

Spelix analyses user-submitted barbell exercise videos (squat, bench press, deadlift) to generate personalised movement coaching feedback. The system uses computer vision (MediaPipe BlazePose) to extract body pose data, scores movement quality across four dimensions, and generates AI-powered coaching recommendations grounded in exercise science research.

### 1.2 Categories of Personal Data

| Data category | GDPR classification | Examples | Retention |
|---------------|---------------------|----------|-----------|
| Account data | Personal data (Art. 6) | Email, display name | Account lifetime |
| Body measurements | Special-category health data (Art. 9) | Height, weight, arm span, femur length | Account lifetime |
| Video recordings | Special-category health data (Art. 9) | Exercise videos showing physical performance and body | 7 days (artifact retention policy) |
| Pose landmarks | Special-category health data (Art. 9) | 33 3D body joint coordinates per frame | Stored as derived metrics only; raw landmarks not persisted |
| Movement quality scores | Special-category health data (Art. 9) | Form scores (0-10), rep metrics, confidence tiers | 24 months |
| Coaching outputs | Personal data (Art. 6) | AI-generated textual coaching feedback | 24 months |
| Consent records | Personal data (Art. 6) | Consent type, timestamp, IP hash, version | Indefinite (append-only audit trail) |
| Coach Brain aggregates | Anonymised (outside GDPR scope) | Categorical coaching patterns with min group n>=20 | Indefinite |

### 1.3 Processing Operations

1. **Video upload**: User uploads exercise video to Supabase Storage via signed TUS URL. Video bytes never transit through the application server.

2. **Quality gate assessment**: Background worker (ARQ) downloads video, runs FFprobe codec validation, extracts pose landmarks for first 5 frames, evaluates body visibility (>=30% mean landmark visibility), resolution (>=720p), and framing checks.

3. **Pose extraction**: MediaPipe BlazePose Heavy model extracts 33 3D landmarks per frame across the full video. Raw landmark arrays are processed in-memory and not persisted to database.

4. **Rep detection and metrics**: Threshold-crossing state machine detects individual repetitions. Per-rep metrics computed: depth angles, eccentric duration, lockout quality, phase of maximum deviation, rep-to-rep consistency.

5. **Form scoring**: Four-dimension scoring system evaluates Movement Quality (safety), Technique, Path & Balance, and Control. Scores are 0-10 with configurable weights.

6. **Keyframe analysis**: Representative frames (start, depth, end per rep) extracted and sent to GPT-4o for visual analysis description.

7. **AI coaching generation**: Claude Sonnet 4.6 generates structured coaching feedback using: rep metrics, form scores, keyframe descriptions, body stats, and retrieved exercise science research (RAG from Qdrant). Coaching follows a cite-then-generate architecture with Chain-of-Verification (CoVe) and faithfulness evaluation.

8. **Coach Brain pattern extraction** (Phase 2+): With explicit Tier 3 consent, anonymised movement patterns are distilled into the Coach Brain collection. Trigger conditions use categorical bins (3-5 categories) for body proportions. Minimum group size n>=20 enforced. Source analysis IDs tracked for consent withdrawal.

9. **Artifact generation**: Annotated video (skeleton overlay), angle time-series plot, PDF report. All artifacts auto-deleted after 7 days.

### 1.4 Data Recipients

| Recipient | Purpose | Data shared | Legal basis |
|-----------|---------|-------------|-------------|
| Supabase (Postgres, Storage, Auth) | Database, file storage, authentication | All user data | Processor agreement |
| Anthropic (Claude API) | Coaching text generation | Rep metrics, form scores, keyframe descriptions, body stats, exercise type | Processor agreement; zero data retention API policy |
| OpenAI (GPT-4o API) | Keyframe visual analysis, exercise auto-detection | Base64-encoded video frame images | Processor agreement; API data not used for training |
| Cohere (Embed + Rerank API) | Embedding generation, search reranking | Exercise science text chunks, coaching query text | Processor agreement |
| Qdrant Cloud | Vector search | Embedded document chunks, coaching pattern vectors | Processor agreement |
| DigitalOcean | Compute infrastructure | All data in transit/processing | Processor agreement |
| Vercel | Frontend hosting | No personal data (static SPA) | N/A — frontend only |

### 1.5 Data Flows

```
User browser
  ├─ Video ──→ Supabase Storage (signed URL, TLS 1.3)
  ├─ Auth ──→ Supabase Auth (JWT, bcrypt-hashed passwords)
  └─ API calls ──→ Caddy reverse proxy (TLS) ──→ FastAPI backend
                                                    ├─→ Supabase Postgres (PgBouncer, TLS)
                                                    ├─→ ARQ Worker (Redis pub/sub)
                                                    │     ├─→ MediaPipe (local CPU)
                                                    │     ├─→ OpenAI GPT-4o (TLS)
                                                    │     ├─→ Anthropic Claude (TLS)
                                                    │     ├─→ Cohere Embed/Rerank (TLS)
                                                    │     └─→ Qdrant Cloud (TLS)
                                                    └─→ SSE coaching stream ──→ User browser
```

---

## 2. Necessity and Proportionality Assessment

*GDPR Article 35(7)(b)*

### 2.1 Necessity

Processing of health data is necessary to fulfil the core service purpose: providing science-based barbell form coaching. Without analysing body movement patterns, joint angles, and physical proportions, the system cannot identify form deviations or generate personalised coaching recommendations.

**Why automated processing is required**: Manual frame-by-frame video analysis by a qualified coach takes 15-30 minutes per video. Automated pose extraction and scoring enables real-time feedback at scale, making coaching accessible to users who cannot afford or access in-person coaching.

**Why health data classification applies**: Per CJEU Grand Chamber (2022) broad interpretation and GDPR Recital 35, body proportion data and movement quality scores "reveal information relating to physical health status." Conservative classification as Article 9 special-category data adopted per ADR-BRAIN-05.

### 2.2 Proportionality

| Principle | Implementation |
|-----------|----------------|
| **Data minimisation** | Raw video deleted after 7 days. Raw pose landmarks processed in-memory only — never persisted to database. Only derived metrics (angles, scores, durations) are stored. |
| **Purpose limitation** | Three-tier consent separates service delivery (Tier 1), health data analysis (Tier 2), and optional aggregate pattern extraction (Tier 3). Each tier has a distinct, documented purpose. |
| **Storage limitation** | Individual analysis artifacts retained 24 months maximum. Video/PDF/plot artifacts deleted after 7 days via automated ARQ cron job. Coach Brain aggregates are anonymised and fall outside GDPR scope. |
| **Accuracy** | 5-tier confidence scoring (Tier 1-5) quantifies pose estimation reliability. Low-confidence results (<0.50) suppress per-rep scores. CoVe verification and faithfulness evaluation gate coaching outputs. |
| **Integrity and confidentiality** | TLS 1.3 for all data in transit. Supabase Row-Level Security on all user-owned tables. PgBouncer connection pooling. No direct foreign keys to auth tables — RLS enforcement only. |

### 2.3 Alternatives Considered

| Alternative | Rejection reason |
|-------------|-----------------|
| No automated processing | Defeats the core value proposition. Manual coaching is the status quo Spelix aims to supplement. |
| Process only non-health data | Not feasible — joint angles and movement patterns are inherently health-related per CJEU interpretation. |
| On-device processing only | MediaPipe supports browser inference but lacks the accuracy of BlazePose Heavy model. Server-side processing with immediate deletion achieves equivalent privacy with better coaching quality. |
| Anonymise before processing | Not possible — coaching requires linking pose data to the specific user's body measurements and exercise history. |

---

## 3. Risk Assessment

*GDPR Article 35(7)(c)*

### 3.1 WP29 High-Risk Criteria Assessment

The following Working Party 29 criteria (Guidelines on DPIA, WP 248 rev.01) apply:

| # | Criterion | Applicable? | Justification |
|---|-----------|-------------|---------------|
| 1 | Evaluation or scoring | **Yes** | Four-dimension form scoring system rates movement quality 0-10 |
| 2 | Automated decision-making with legal/significant effect | **Partial** | Coaching recommendations may influence training decisions; no legal effect |
| 3 | Systematic monitoring | **Yes** | Repeated video analysis of exercise performance over time |
| 4 | Sensitive data | **Yes** | Health data under GDPR Article 9 |
| 5 | Data processed on a large scale | Not yet | Early stage; monitoring required as user base grows |
| 6 | Matching or combining datasets | **Yes** | Coach Brain combines patterns across users (anonymised) |
| 7 | Data concerning vulnerable data subjects | No | General adult population; no special vulnerability |
| 8 | Innovative use of technology | **Yes** | AI/ML for movement analysis and coaching generation |
| 9 | Data transfer outside EU | **Yes** | API calls to US-based providers (Anthropic, OpenAI, Cohere) |

**Result**: 6 of 9 criteria met. DPIA is mandatory per WP29 guidance (>=2 criteria triggers requirement).

### 3.2 Identified Risks

| Risk ID | Risk | Likelihood | Severity | Inherent risk | Mitigation | Residual risk |
|---------|------|------------|----------|---------------|------------|---------------|
| R-01 | **Re-identification from Coach Brain aggregates** | Low | High | Medium | Categorical bins (3-5 categories), min group n>=20, no precise measurements stored (NFR-PRIV-03/04) | Low |
| R-02 | **Data breach exposing video/health data** | Low | High | Medium | 7-day artifact deletion, TLS 1.3, RLS policies, encrypted storage at rest, no video bytes transit through app server | Low |
| R-03 | **Inaccurate coaching causing injury** | Medium | High | High | 5-tier confidence scoring, low-confidence suppression, mandatory Movement Quality warning at score <3.0, mandatory educational disclaimer on all coaching output, CoVe verification, faithfulness gate | Medium |
| R-04 | **Algorithmic bias in scoring** | Medium | Medium | Medium | Exercise-specific scoring dimensions, ThresholdConfig with provenance citations, expert reviewer PR-based approval flow, per-analysis eval scores for monitoring | Low |
| R-05 | **Third-party API data exposure** | Low | Medium | Low | Zero data retention policies with Anthropic/OpenAI, processor agreements, no raw video sent to LLM APIs (only derived metrics and keyframe images) | Low |
| R-06 | **Consent fatigue / invalid consent** | Medium | Medium | Medium | Three-tier consent with distinct interaction points, service functions without Tier 3, clear withdrawal mechanism, append-only audit trail | Low |
| R-07 | **Cross-border transfer risks** | Medium | Medium | Medium | Standard Contractual Clauses with US providers, no EU adequacy decision dependency, processor agreements | Low |
| R-08 | **Excessive data retention** | Low | Low | Low | 7-day artifact deletion, 24-month analysis retention, automated cleanup cron | Low |
| R-09 | **Function creep in Coach Brain** | Low | Medium | Low | Strict phase gating (seed corpus only in Phase 2), distillation requires expert review (Phase 3), ToS prohibits reverse engineering (NFR-PRIV-07) | Low |

---

## 4. Mitigation Measures

*GDPR Article 35(7)(d)*

### 4.1 Technical Measures

| Measure | Implementation | SRS reference |
|---------|----------------|---------------|
| **Encryption in transit** | TLS 1.3 on all connections (Caddy auto-cert, Supabase managed, API provider endpoints) | Infrastructure |
| **Encryption at rest** | Supabase managed encryption, DigitalOcean volume encryption | Infrastructure |
| **Row-Level Security** | All user-owned tables enforce `user_id = auth.uid()` via Supabase RLS policies. No DDL foreign keys to auth schema. | NFR-PRIV-01 |
| **Append-only consent audit trail** | Consent records are never updated or deleted. Withdrawals insert new rows with `granted=false, withdrawn_at=timestamp`. Full audit trail preserved. | NFR-PRIV-02 |
| **Categorical binning** | Coach Brain trigger conditions use 3-5 category bins for body proportions. Precise measurements never stored in Coach Brain. Bin boundaries from sports science literature. | NFR-PRIV-03 |
| **k-anonymity enforcement** | Minimum group size n>=20 before surfacing bin-specific patterns. At early scale, reduce quasi-identifiers to 2-3 attributes. | NFR-PRIV-04 |
| **Artifact retention** | Video, annotated video, PDF, plot auto-deleted after 7 days via nightly ARQ cron. Analysis rows and scores retained (no artifact bytes). | Data minimisation |
| **Consent withdrawal cascade** | On Tier 3 withdrawal: ARQ job removes user's analysis IDs from `source_analysis_ids` across all Coach Brain entries. Entries left empty with `confirmation_count < 3` are soft-deleted. | FR-BRAIN-16 |
| **Confidence-gated output** | 5-tier confidence scoring. Very Low (<0.50) suppresses per-rep scores. Movement Quality score <3.0 triggers mandatory warning. | FR-CVPL-20..25 |
| **Coaching output verification** | CoVe loop (max 2 iterations), faithfulness evaluation (HHEM-style LLM judge, threshold 0.8), citation-grounded generation | FR-AICP-08 |
| **Internal metadata isolation** | Coach Brain confidence scores, source_analysis_ids, confirmation_count never exposed in user-facing outputs. Admin/reviewer only. | NFR-PRIV-07 |

### 4.2 Organisational Measures

| Measure | Status |
|---------|--------|
| **DPO appointment** | Recommended before public launch. Not yet appointed at current private beta stage. |
| **Privacy Policy** | Must include all GDPR Article 13 obligations: health data identification, purpose listing, legal basis mapping, named recipients, retention periods, automated decision-making disclosure, withdrawal rights. (NFR-PRIV-05) |
| **Processor agreements** | Required with all data sub-processors: Supabase, Anthropic, OpenAI, Cohere, Qdrant Cloud, DigitalOcean. |
| **Expert review of coaching patterns** | ThresholdConfig changes require PR review. Coach Brain distillation (Phase 3) requires certified coach review before promotion. |
| **Incident response** | Data breach notification within 72 hours per GDPR Article 33. User notification without undue delay per Article 34 where high risk to rights/freedoms. |
| **Regular DPIA review** | This DPIA must be reviewed: (a) before each new phase launch, (b) when processing operations change materially, (c) annually at minimum. |

### 4.3 Data Subject Rights

| Right | Implementation |
|-------|----------------|
| **Access (Art. 15)** | `GET /api/v1/analyses` returns all user analyses. `GET /api/v1/consent` returns consent records. Profile data via `GET /api/v1/profiles`. |
| **Rectification (Art. 16)** | Profile data editable via `PUT /api/v1/profiles`. Analysis data is system-generated and not subject to rectification. |
| **Erasure (Art. 17)** | Account deletion via `DELETE /api/v1/account` triggers: consent withdrawal cascade (FR-BRAIN-16), Supabase auth user deletion, cascade delete of analyses/profiles/consent records. |
| **Restriction (Art. 18)** | Consent withdrawal for Tier 2 prevents further health data analysis. Consent withdrawal for Tier 3 removes contribution to Coach Brain. |
| **Portability (Art. 20)** | PDF export includes all analysis scores and coaching text. JSON export of analysis data available via API. |
| **Object (Art. 21)** | Users may withdraw consent at any time. Service continues functioning without Tier 3 (aggregate) consent. |
| **Automated decisions (Art. 22)** | Coaching is advisory only — no legally binding or similarly significant automated decisions. Educational disclaimer on all outputs. Users retain full autonomy over training decisions. |

---

## 5. Consultation

### 5.1 Data Subject Consultation

Three-tier consent model (FR-BRAIN-11) provides granular control:
- **Tier 1**: General service consent (contract performance, Art. 6(1)(b))
- **Tier 2**: Explicit health data processing consent (Art. 9(2)(a)) — separate interaction, freely given
- **Tier 3**: Optional aggregate pattern contribution — service functions fully without it

Consent withdrawal available at any time through dedicated UI and API endpoints.

### 5.2 Supervisory Authority Consultation

Prior consultation under Article 36 is not currently required as residual risks have been mitigated to acceptable levels through the measures described in Section 4. This assessment should be revisited if:
- User base exceeds 10,000 active users
- Processing operations expand beyond current scope
- New high-risk criteria from Section 3.1 become applicable

---

## 6. Review Schedule

| Trigger | Action |
|---------|--------|
| Phase 3 launch (distillation pipeline) | Full DPIA review — new automated processing of Coach Brain entries |
| Phase 4 launch (per-athlete memory) | Full DPIA review — episodic memory introduces longitudinal profiling |
| User base exceeds 1,000 | Review large-scale processing criterion |
| Material change to processing | Targeted review of affected sections |
| Annual review | Comprehensive review regardless of changes |
| Regulatory guidance update | Targeted review against new guidance |

---

*This DPIA satisfies FR-BRAIN-15 and NFR-PRIV-06. It must be reviewed before each phase transition and maintained as a living document.*
