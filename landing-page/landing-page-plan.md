# Landing Page Plan — Spelix Private Beta

**Created:** 2026-04-14
**Status:** Draft for founder review
**Target ship (V1):** 2026-04-15 (end of Day 2 of 19-day L2 sprint; STRATEGY.md v3 hard gate)
**Target ship (V2 polish):** rolling 2026-05-04 → 2026-05-14 (post-L2, Sprint BETA)
**Updated:** 2026-04-14 (v2) — re-aligned to STRATEGY.md v3 compressed timeline (May 3 gate, not May 9).
**Route:** `spelix.app/` — replaces current `frontend/src/pages/HomePage.tsx`
**Authoritative sources:** `STRATEGY.md`, `docs/SRS.md` v2.1, `decisions.md`, `frontend/CLAUDE.md`
**Origin:** founder draft (Claude chat, 2026-04-14) → analyzed and refined against codebase + SRS + strategy

---

## 0. How This Plan Is Structured

Sections 1–4 set the strategic and compliance frame — **read first, edit second**. Sections 5–6 specify the page. Sections 7–10 cover flow, instrumentation, assets, and code. Section 11 is the acceptance checklist. Sections 12–14 log open decisions and what changed from the draft.

Proposed copy in Section 6 is a strong starting point, not final — every headline and paragraph is expected to go through one editorial pass with the founder before shipping.

---

## 1. Strategic Context

**Why this landing page exists.** Per `STRATEGY.md` v3 Day 1-2 of the 19-day L2 sprint (Apr 14-15), spelix.app needs to flip from "I built this" (the current HomePage placeholder) to a beta-recruitment surface. The L2 hard gate is 2026-05-03 and requires landing live on prod by end of Day 2 as one of two parallel Day 1-2 hard gates (the other is expert PDF upload wiring). Target beta-user volume by L4 (2026-07-01, interview start) is 40-60 approved users. The page is simultaneously the **recruiter-readable artifact** for Fall 2026 AI-lab interview cycles — the public front door to the interview narrative.

**What this landing page is NOT.**

- Not a commercial GTM surface — L4 is explicitly off-table for 2026 (`STRATEGY.md` §Level Progression).
- Not a viral acquisition funnel — organic r/weightroom post is a late-May Sprint GROW signal; this page is the warm-network conversion surface first.
- Not a product tour — the logged-in experience (Upload → Status → Results) is the real product. The landing page's job is to earn the signup, not replace the demo.
- Not the disclaimer page — the page has a short disclaimer block and links to the full `public/beta-terms.md` (separate file, created alongside).

**Two audiences, one page.** Landing pages usually serve one primary audience. Spelix's page serves two who happen to respond to the same content: serious recreational lifters and AI-lab recruiters. Both want evidence-grounded specificity over hype. The page leans into that.

**Budget reality.** `STRATEGY.md` v3 runs a full-time sprint (10-15 hrs/day). Day 1-2 carries two parallel hard gates: landing V1 (this plan) on Track A, and expert PDF upload wiring on Track B. Track A must ship V1 by end of Day 2 (Apr 15) so Track B work on expert onboarding can complete in parallel. Hence the **V1/V2 split** in Section 5 — V1 is the minimum viable subset that hits the Day 2 gate; V2 polish rolls into Sprint BETA (May 4-14) alongside the broader frontend redesign.

---

## 2. Target Audience

Three personas, all of whom end up at the same page. The copy must speak to all three simultaneously rather than layering mode-switch blocks.

### 2.1 The Serious Recreational Lifter (primary conversion target)

- 3-5 years of lifting, has filmed themselves, has tried at least one AI form-check app and been unimpressed.
- Knows something is off in their squat/bench/deadlift but can't precisely name it.
- Sources: warm network (McMaster barbell club, kinesiology partner's network, gym friends), r/weightroom (late May in Sprint GROW, one attempt, per STRATEGY.md v3).
- **Converts on:** the citation differentiator, the kinesiology-specialist credential, the per-rep Control dimension (no other app scores this), and explicit naming of why existing apps are unreliable.

### 2.2 The Evidence-Oriented Lifter (high-value secondary)

- Reads r/weightroom and r/powerlifting. Skeptical of any "AI" claim by default.
- Will leave immediately if they see unverified accuracy numbers ("95% accurate") or hand-wavy "science-based" without a source.
- **Converts on:** JMIR-style statistic framing of the category failure, the honest confidence display (Spelix admits uncertainty), the expert-validated corpus curation, and the absence of medical/clinical claims.

### 2.3 The AI-Lab Recruiter / Technical Reviewer (lurker, judges without converting)

- Comes via ONE_PAGER or interview application. Skims the page in 30 seconds to form an opinion about the candidate.
- Cares whether the product looks real, whether the technical architecture hints feel rigorous, and whether the founder writes with precision.
- **Respects:** absence of buzzword spam, a hero screenshot of the actual product (not stock), the research-foundation narrative, and a visible "private beta, not a substitute for a qualified coach" disclaimer.

**Tone that serves all three:** Cronometer-style — calm, evidence-forward, specific, slightly technical, confident because it's right, never loud. Avoid founder voice first-person ("I built this because…"). Avoid revolutionary/future-of language. Short sentences. Named numbers (33 landmarks, 4 dimensions, per-rep metrics).

---

## 3. Hard Constraints

These are non-negotiable. Violating any of them triggers SRS, SaMD/FTC, GDPR, or strategy risk.

### 3.1 Language Rules (SRS §2.5, Appendix D, NFR-PRIV-01)

**Never use on the page or in any marketing copy:**

- "injury risk," "injury prevention," "prevents injuries," "risk of injury"
- "safety score" (internal `form_score_safety` → user label is always "Movement Quality")
- "medical advice," "diagnosis," "treats," "clinical"
- "95% accurate" or any self-reported accuracy claim without a published methodology
- "revolutionary," "the future of fitness," "next-gen"
- "cure," "fix," "correct" (re: movement — use "improve," "refine")

**Use instead:**

- "Movement Quality" (the single permitted label for the safety dimension)
- "form improvement," "movement quality," "coaching feedback," "technique"
- "wellness and performance optimization" framing — FDA General Wellness guidance-aligned
- "grounded in peer-reviewed research" (not "scientifically proven")
- "coaching feedback" (not "diagnosis")

### 3.2 Mandatory Disclaimers

**Small disclaimer on the landing page itself (required under NFR-USAB-06 analog; verbatim wording from SRS §265):**

> *"Spelix is currently in private beta. This feedback is for educational and performance purposes only. It is not a substitute for advice from a qualified coach, physiotherapist, or medical professional."*

This appears at minimum: (a) directly under the hero CTA, and (b) in the page footer. Every page footer on spelix.app should carry the same text — add it to `AppLayout.tsx` in the same branch.

**Linked full terms:** `public/beta-terms.md` — short, 2-paragraph beta terms per `STRATEGY.md` Day 1-2. Created in the same PR as the landing page.

### 3.3 Kinesiology Expert Credential (SRS §829 verbatim)

The only permitted phrasing for the expert is:

> *"AI coaching validated by a Kinesiology specialist (B.Sc. candidate). All coaching claims are grounded in peer-reviewed literature reviewed and curated by a qualified expert."*

**Do not** say "certified kinesiologist," "kinesiology expert," "coach," "doctor," or "professional." The reviewer is a Year 3 Pre-Med kinesiology student, credentialled as a B.Sc. candidate. Overstating credentials is both SRS-prohibited and an FTC exposure risk.

A shortened variant for prose flow is acceptable on secondary mentions: *"our kinesiology-specialist collaborator"* or *"a kinesiology-qualified B.Sc. candidate."*

### 3.4 Privacy & Data Framing (SRS NFR-PRIV-01 through -07, GDPR Article 35 DPIA)

The page must state honestly:

- Raw video is deleted after processing; retained derivatives are skeleton/pose data and metrics, not footage.
- Analysis uses automated decision-making on health-adjacent data. Users sign consent (3-tier GDPR Article 9) at signup. A DPIA is on file.
- Users can export everything and delete their account at any time; data is not sold or shared.
- The Coach Brain's learning loop applies k-anonymity (n ≥ 20) before any bin-specific pattern surfaces.

The page doesn't need to name GDPR Article 35 or DPIA by acronym — plain language is better — but it must be accurate to the underlying commitment.

### 3.5 Confidence Presentation (FR-CVPL-25)

User-facing confidence is **always categorical**: High / Moderate / Low / Very Low. Never display raw decimals on the landing page, screenshots used on the landing page, or any marketing asset. The STRATEGY.md "5-tier confidence" language refers to the internal modelling pipeline (Tier 5 per-rep confidence = 10th percentile of phase-adjusted frame confidences, FR-CVPL-24) and is appropriate for a technical blog post, not a landing-page claim.

### 3.6 Private-Repo Stance (STRATEGY.md §Privacy Policy)

Source stays in the private repo. The landing page:

- Does **not** link to the source on GitHub.
- Does **not** name third-party libraries (LangGraph, Qdrant, Cohere, FastAPI, React, etc.) as selling points.
- Does link to blog posts (once published, Weeks 3-4), ONE_PAGER, and unlisted Loom walkthrough when those exist.

---

## 4. Positioning & Core Claim

**The positioning sentence** (internal — not necessarily on the page verbatim):

> Spelix is the only barbell coaching app where every piece of coaching feedback is grounded in peer-reviewed biomechanics research, with a kinesiology-specialist collaborator curating every paper that shapes coaching output.

**The single most important sentence of the page** (hero headline candidates — pick one, section 6.1):

- Option A (claim-forward): *"Barbell form coaching where every piece of feedback cites its source."*
- Option B (challenge-forward): *"Your squat isn't random. Your coaching shouldn't be either."*
- Option C (category-forward): *"Science-grounded AI form coaching — built with a kinesiology specialist."*

**Recommendation: Option A.** It is the tightest claim, differentiates Spelix from every competitor in under ten words, and maps 1:1 to the citation differentiator that actually exists in the shipped Phase 2 product.

---

## 5. Page Architecture

Eight sections, top to bottom. Each section is independently loadable and independently skippable. V1 ships a minimum-viable subset by end of Day 2 (Apr 15); V2 polish rolls into Sprint BETA (May 4-14) alongside the broader frontend redesign.

| # | Section | V1 (Apr 15) | V2 (May 4-14) | Rough word count |
|---|---------|-------------|------------|------------------|
| 1 | Hero | ✓ | (refine copy) | 60-80 |
| 2 | The Problem | ✓ | (refine copy) | 180-220 |
| 3 | How Spelix Works | ✓ | (expand screenshots) | 140-180 |
| 4 | What Makes Spelix Different | ✓ (all 3 differentiators) | — | 280-340 |
| 5 | The Four Dimensions | — | ✓ | 180-220 |
| 6 | On The Roadmap | — | ✓ | 100-140 |
| 7 | Privacy & Disclaimer | ✓ | (expand if user sessions raise issues) | 100-140 |
| 8 | Join The Private Beta | ✓ | (add quote from beta user if available) | 80-120 |

**V1 ships with sections 1, 2, 3, 4, 7, 8** — all three differentiators make the V1 cut because the product's differentiation *is* the page's differentiation. Section 5 (Four Dimensions detail) and Section 6 (Roadmap) are deferred to V2 polish.

**Section 5 is optional even in V2** — if Sprint BETA user sessions (May 4-14) show confusion about what the four scores mean, promote Section 5 into V2. If they don't, Section 5 can ship later (Sprint GROW, May 15 - Jul 1).

---

## 6. Section Specifications

All copy below is a proposed first draft. Founder editorial pass expected before implementation.

### 6.1 Hero (V1)

**Purpose:** Stop the scroll. Declare the claim. Show the product.

**Headline (recommended Option A):**

> *"Barbell form coaching where every piece of feedback cites its source."*

**Sub-headline (~30 words):**

> *"Spelix analyses your squat, bench, or deadlift with computer vision and generates structured coaching grounded in peer-reviewed biomechanics literature. Every claim is traceable to the study behind it."*

**Hero visual:** A single high-fidelity screenshot — the Results page with:

- The streaming coaching panel mid-generation (text partially rendered)
- One visible citation tooltip expanded, showing study title + authors + year
- The 4-dimension FormScoreCards row visible below
- The ConfidenceBadge showing "Moderate" (not a decimal)

No stock photos. No rendered 3D. The actual shipped UI. Capture via Playwright MCP against a real analysis on spelix.app.

**Primary CTA:** Email capture inline with the hero.
- Input placeholder: *"your@email.com"*
- Button: *"Request private-beta access"*
- Micro-copy under the button: *"Free during beta · Limited spots · We reply within a few days"*

**Disclaimer badge (directly under CTA):**

> *"Private beta. For educational and performance purposes only — not a substitute for a qualified coach or medical professional. [Read beta terms →]"*

(Link points to `/beta-terms`, a static page that renders `public/beta-terms.md`.)

### 6.2 The Problem (V1)

**Purpose:** Identification. The reader nods along. Trust is established before Spelix sells anything.

**Section headline:**

> *"You've watched yourself lift. You've tried the apps. You know the problem."*

**Lead paragraph (~60 words):**

> *"Every form-check app promises AI-powered feedback. In practice, you get a score with no explanation, advice with no source, and answers that change every time you re-run the same clip. The best existing apps are closer to a confident guess with a clean UI than to coaching."*

**Three failure modes — each as a short block with a bold lead:**

**No source.**
> *"Studies evaluating AI fitness applications against published guidelines have found that only 8% provide any reference to the source of their recommendations (JMIR, 2024). The other 92% just tell you things. An app that confidently asserts your knee angle is off without showing why is not coaching — it is an opinion with a progress bar."*

**No consistency.**
> *"Across the most popular consumer form-check apps, users regularly report that the same video clip produces different scores and different advice on successive runs. Non-deterministic coaching is not coaching — it is noise with a UI."*

**One body fits all.**
> *"Real biomechanics is individual. A lifter with long femurs squats differently from one with a short torso. Someone whose arm span exceeds their height has a different optimal deadlift setup than someone whose span is shorter. Most apps calibrate advice to a generic average human who does not exist."*

**Closing line (~20 words):**

> *"The apps exist. The apps are widely used. And the fitness community has known they are not enough for years."*

### 6.3 How Spelix Works (V1)

**Purpose:** Walk the reader through the product experience in plain language. Technology is shown, not sold.

**Section headline:**

> *"Three steps, one lift at a time."*

**Step 1 — Upload your video.** (~45 words)
> *"Film your squat, bench, or deadlift from the side with your phone. One working set is enough. Spelix accepts standard phone video — no special camera, rig, or studio required."*

**Step 2 — Spelix analyses every rep.** (~55 words)
> *"Computer vision tracks 33 body landmarks per frame across your entire lift. Each rep is measured individually: joint angles at key phases, bar path, eccentric tempo, bilateral balance, and sticking-point location. You will see things about your lift that have never been quantified for you before."*

**Step 3 — You get coaching that cites its sources.** (~55 words)
> *"Results include a streaming written coaching breakdown across four dimensions — Movement Quality, Technique, Path & Balance, and Control — with each claim grounded in peer-reviewed exercise science. Hover on any coaching sentence to see the study it is drawn from: title, authors, year, link."*

**Visual treatment:** Three numbered cards side-by-side on desktop, stacked on mobile. Each card has a small graphical element (upload icon, skeleton overlay graphic, citation tooltip graphic) rather than a photo.

**What you get** (bullet list under the three steps):

- Per-rep biomechanical scores (so fatigue patterns across your set are visible)
- Annotated video with skeleton overlay showing what the computer vision detected
- Downloadable PDF report with full session analysis
- Follow-up chat — ask the system anything about your analysis

### 6.4 What Makes Spelix Different (V1 — all three)

**Section headline:**

> *"Three things no other app does."*

**Differentiator 1: Every claim has a source you can read.**

Sub-headline: *"The research foundation."*

Copy (~100 words):
> *"Spelix generates its coaching through retrieval over a curated corpus of peer-reviewed biomechanics and exercise-science literature — systematic reviews, randomised trials, and validated clinical studies, each selected and approved by a kinesiology-qualified collaborator. When Spelix tells you something about your lift, it is not because a language model decided to say it. It is because the claim is directly grounded in published research that you can click through and read. Studies evaluating AI fitness apps against published guidelines have found only 8% of them provide any source reference. Spelix was designed from day one around the principle that ungrounded coaching is worse than no coaching — because it is confident noise."*

Visual: Expanded citation tooltip mockup, showing study title + authors + year + DOI + relevance excerpt.

**Differentiator 2: Built with a kinesiology specialist, not just a dataset.**

Sub-headline: *"Expert-validated research corpus."*

Copy (~90 words):
> *"Every paper in Spelix's research corpus is reviewed and approved by a kinesiology-qualified B.Sc. candidate before it influences coaching output. The angle thresholds Spelix uses to evaluate your squat depth, knee tracking, and bar path were validated by a human expert against published biomechanics evidence — not generated by an AI and shipped. Most CV-based form-analysis systems use angle thresholds derived from population averages or generated algorithmically. Spelix's thresholds are anchored to peer-reviewed evidence and reviewed by a specialist who has actually read the papers behind them."*

**Canonical credit line** (footer of this section, verbatim per SRS §829):
> *"AI coaching validated by a Kinesiology specialist (B.Sc. candidate). All coaching claims are grounded in peer-reviewed literature reviewed and curated by a qualified expert."*

Visual: Small profile block — icon or silhouette, name (or "Kinesiology specialist" if pseudonymous), field ("Kinesiology, B.Sc. candidate"), one-sentence quote about corpus curation.

**Differentiator 3: The Coach Brain — coaching intelligence that compounds.**

Sub-headline: *"Gets more specific with every analysis."*

Copy (~120 words):
> *"Most AI coaching apps are static. The model they ship today is the model you get forever. The advice you receive in month one is the advice you receive in month twelve."*
>
> *"Spelix is different. At the heart of the platform sits a coaching intelligence layer called the Coach Brain — a system that distils validated coaching patterns from real analysis outcomes, cross-referenced against the research corpus, reviewed by the kinesiology collaborator, and continuously refined. The Coach Brain does not apply generic AI reasoning to your lift. It applies coaching knowledge that has been tested, validated, and accumulated specifically for barbell athletes."*
>
> *"The more lifters Spelix analyses, the more specific its coaching becomes. Patterns that emerge across body types, stance widths, and experience levels get learned, validated, and applied to future lifters. This is compounding coaching intelligence — something no other app in this category has built."*

**Avoid in this block:** "RAG," "Qdrant," "vector database," "embeddings," "distillation," "LangGraph," "LLM," "GPT," "Claude." Use "coaching intelligence layer," "validated coaching patterns," "compounds with every analysis," "the Coach Brain."

Visual: Simple concept illustration of a growing node network — abstract, suggestive of accumulating knowledge without being technical.

### 6.5 The Four Dimensions (V2)

**Purpose:** Impress the skeptic who assumes Spelix is "another angle detector." Show the depth of what is measured.

**Section headline:**

> *"Four dimensions, calibrated to your body."*

Presentation: 2×2 card grid (stacks on mobile). Each card: bold dimension name, one-paragraph description, small visual accent.

**Movement Quality** (~50 words):
> *"Evaluates movement patterns that affect long-term joint health and loading quality. Valgus angle, lateral shift, trunk inclination. Most apps skip this dimension entirely. Spelix calibrates thresholds to your declared body stats and experience level."*

**Technique** (~45 words):
> *"Rates body positioning for effective force production. Joint angles at key phases, stance width, depth, grip, setup posture. This dimension evaluates mechanical efficiency, not just whether the lift looks right to a passing observer."*

**Control** (~55 words):
> *"The dimension no other consumer app scores. How consistent is your eccentric tempo? How stable is your form across reps one through eight? Do you rush the descent on your harder reps? Control is where fatigue becomes visible before form changes meaningfully — the earliest signal in your training."*

**Path & Balance** (~45 words):
> *"Where does your barbell travel? How far does it deviate from vertical? How symmetric is the load between left and right sides? Bar-path efficiency determines how much of your effort moves the weight versus compensates for drift."*

**Footer line (~25 words):**
> *"These are not just scores. Each dimension is grounded in biomechanics literature, and each dimension's thresholds are calibrated to the body stats you declare on your profile."*

### 6.6 On The Roadmap (V2)

**Purpose:** Show trajectory. Beta users are not just getting a feature snapshot — they are shaping what comes next.

**Section headline:**

> *"What's next — built with beta-user feedback."*

**Three items, each ~30-40 words:**

**Progress tracking across sessions**
> *"See how your squat depth, bar-path variance, and eccentric consistency have changed week over week. The Coach Brain tracks not just today's lift but the full arc of your training."*

**Adaptive coaching**
> *"Future Spelix will reason across your full analysis history, adjusting its advice to your specific patterns, weak points, and progress — not just the session in front of it."*

**Per-athlete coaching memory**
> *"The coaching intelligence Spelix builds about barbell lifting in general will eventually compound with the coaching intelligence it builds specifically about you — how your body responds, which cues land, which do not."*

**Framing line (bottom of section):**
> *"These features are under active development. Spelix is currently in private beta, and beta users shape the roadmap."*

### 6.7 Privacy & Disclaimer (V1)

**Purpose:** Build trust with the technically careful and ethically literate lifter. Signal maturity. Most indie apps skip this — including it differentiates.

**Section headline:**

> *"What Spelix does with your video — and what it does not do."*

**Three blocks, each ~45-55 words:**

**Your video is not kept.**
> *"Raw video is deleted after processing. What Spelix retains is your skeleton data — joint coordinates and derived metrics — not your footage. You can view and download your data at any time from your profile, and you can delete your account completely whenever you want."*

**Spelix is not a medical device.**
> *"Spelix analyses movement patterns and grounds coaching in the published biomechanics literature. It does not diagnose anything, and it is not a substitute for a physiotherapist, a qualified coach, or a medical professional. All feedback is for educational and performance purposes only."*

**Your data belongs to you.**
> *"Your analyses are yours. Spelix does not sell or share your data. Anonymised patterns may inform the Coach Brain's learning layer only after passing a minimum-group-size threshold that prevents any individual lifter from being identifiable."*

### 6.8 Join The Private Beta (V1)

**Purpose:** Close on emotion. Convert.

**Section headline (emotional):**
> *"You have filmed your lifts. You have watched them back. You have wondered what you were missing."*

**Sub-copy (~50 words):**
> *"Spelix was built by someone who asked the same questions and went looking for the answers in the research. The result is an app that shows you the study behind every piece of coaching it gives you. Beta access is free, limited, and open now."*

**"What beta users get" bullets (4 items, ~60 words total):**

- Full access to all current features, completely free
- A direct line to the team — feedback shapes what ships next
- Early access to every new feature before public launch
- The knowledge that your analyses help calibrate the system for athletes like you

**Second email capture (same inputs as hero):**
- Input: email
- Button: *"Join the private beta"*
- Micro-copy: *"Free during beta · No credit card · You'll receive an invite link within a few days of signing up."*

**Final disclaimer line:**
> *"Spelix is in private beta. Feedback is for educational and performance purposes only — not a substitute for a qualified coach or medical professional."*

---

## 7. CTA Flow — Email Capture & Manual Approval

**Why manual approval throughout the sprint + Sprint BETA.** Per `STRATEGY.md` v3, the private beta stays **manual approval** through at least Sprint BETA (May 4-14): "Rolling invites from the beta-requests queue: approve in batches of 5, observe for UX issues, fix, invite next batch. Target by May 14: 15-20 approved beta users." No auto-gate is planned for L3 (2026-05-15) or L4 (2026-07-01) in v3. Manual approval doubles as a selection filter and a data source for the first Retention/Feedback metrics cut. If volume ever exceeds ~30/week, re-evaluate.

**Model: email capture → manual invite.**

1. User enters email in either hero or final CTA form.
2. Email posts to `POST /api/v1/beta/requests` (new endpoint, backend).
3. Backend inserts into a new `beta_requests` table (columns: `id`, `email`, `source` (hero/final-cta/reddit/dm), `consented_to_beta_terms bool`, `created_at`, `approved_at`, `approved_by`, `invite_sent_at`, `invite_token`).
4. User sees inline confirmation: *"Thanks — we'll email you an invite within a few days."*
5. Founder reviews the table daily (admin page, Tier 2 FR-ADMN-* scope — added as a new card on `AdminPage.tsx`).
6. Founder clicks "Approve" → backend generates a single-use invite token → sends email via existing transactional provider with a link to `/signup?invite=TOKEN`.
7. `/signup` reads `?invite=` query param, validates the token server-side, pre-fills the email field as read-only, and gates signup completion on token validity.

**Data model constraint (per `CLAUDE.md` + SRS):**
- `beta_requests.status` as `VARCHAR(30) CHECK (status IN ('pending', 'approved', 'rejected'))` — matches the Spelix schema rules.
- RLS: only admins can read or update. Anonymous (unauth) clients can only INSERT.
- Email gets a lowercase + trim normalisation in the API layer before insert.

**Alternative rejected:** Letting anyone sign up and flagging `pending_beta_approval` on the user row — more state to manage, couples the landing capture flow to full Supabase Auth signup which wants email verification. Simpler to keep email capture as a pre-auth list.

**Consent checkbox UX (hero + final form):**
- Single unchecked checkbox: *"I have read the [beta terms](/beta-terms) and agree to them."*
- `aria-disabled=true` on submit until the checkbox is checked.
- Matches the existing `UploadPage` pattern (`aria-disabled` on dual-dropdown validation).

---

## 8. Instrumentation

`STRATEGY.md` v3 Day 1-2 requires PostHog instrumentation for landing events (`landing_view`, `landing_email_submit_*`). Recommendation: **PostHog cloud free tier** — autocaptures clicks + pageviews, easier to ship inside the Day 1-2 gate, has a free self-hosted path later if required.

**Events to fire from the landing page:**

| Event | Where | Properties |
|-------|-------|------------|
| `landing_view` | On mount | `referrer`, `utm_*` |
| `landing_scroll_depth` | Intersection observer on section boundaries | `section` (1-8), `percent` |
| `landing_email_submit_attempt` | On form submit | `cta_location` (hero / final), `email_domain` |
| `landing_email_submit_success` | On 200 response | `cta_location`, `request_id` |
| `landing_email_submit_error` | On non-2xx | `cta_location`, `error_code` |
| `landing_beta_terms_click` | On disclaimer link click | `cta_location` |
| `landing_citation_tooltip_demo_click` | If hero screenshot is interactive | — |

**Strategy-aligned events that already need to exist** (landing page wires the first of them):

- `signup_complete` (triggered on `/signup` success with invite token)
- `first_upload` (first successful TUS upload)
- `upload_complete` (analysis reaches `completed` status)
- `coaching_view_duration` (time spent on `/results/:id` with coaching visible)
- `thumbs_up` / `thumbs_down` (when feedback widget lands)
- `pdf_download`
- `return_visit` (same authenticated user session >24h apart)

Landing PR only needs to wire the `landing_*` events — the rest live on their own routes.

---

## 9. Visual Assets Required

**Must-have for V1 (end of Day 2, Apr 15):**

1. `public/landing/hero-results.png` — Results page screenshot, streaming coaching + citation tooltip + 4-dim cards visible. Capture via Playwright MCP against a real `completed` analysis on spelix.app. 2x retina.
2. `public/landing/annotated-skeleton.png` — One frame of the annotated video with MediaPipe skeleton overlay, used in Step 2 of "How It Works."
3. `public/landing/citation-tooltip.png` — Zoomed crop of an expanded citation tooltip, used in Differentiator 1.
4. Logo / wordmark — existing `public/favicon.svg` can be promoted, or a simple text wordmark in the same typeface as the hero.

**V2 additions (rolling, Sprint BETA May 4-14):**

5. `public/landing/demo.gif` (if a demo GIF is recorded during the sprint or Sprint BETA it can double as a hero asset) — 20-30 sec looping MP4/WebM, muted, autoplay. Compressed.
6. `public/landing/coach-brain-concept.svg` — abstract growing-node illustration for Differentiator 3.
7. `public/landing/four-dimensions-grid.svg` — icon set for Section 5 card grid.
8. `public/landing/kinesiology-specialist.svg` — stylised profile icon for Differentiator 2.

All assets commit to `frontend/public/landing/` so Vite serves them statically at `/landing/*`.

---

## 10. Technical Implementation Notes

**Framework alignment:** React 19 + Vite 8 + Tailwind CSS 4 + shadcn/ui + React Router v6 (per `frontend/CLAUDE.md`). No Next.js, no `"use client"`, no App Router.

**Route changes (`src/routes.tsx`):**

- Current `/` → `HomePage` (minimal placeholder).
- New `/` → `LandingPage.tsx` (new file in `src/pages/`).
- New `/beta-terms` → `BetaTermsPage.tsx` that renders the markdown from `public/beta-terms.md`. Use `react-markdown` (add dependency).
- Keep the auth-redirect behaviour from the current `HomePage`: on mount, check `supabase.auth.getSession()`. If session exists → `navigate("/upload", { replace: true })`. Otherwise render the landing marketing content. This preserves the existing UX for logged-in users.

**Component layout:**

```
src/pages/LandingPage.tsx         # Top-level page (auth redirect + section composition)
src/pages/BetaTermsPage.tsx       # Static terms renderer
src/components/landing/
  Hero.tsx
  EmailCaptureForm.tsx            # Reused in Hero + FinalCTA
  ProblemSection.tsx
  HowItWorksSection.tsx
  DifferentiatorsSection.tsx      # Wraps three DifferentiatorCard children
  DifferentiatorCard.tsx
  FourDimensionsSection.tsx       # V2
  RoadmapSection.tsx              # V2
  PrivacySection.tsx
  FinalCtaSection.tsx
  BetaDisclaimer.tsx              # Shared — appears under CTAs and in footer
  SectionWrapper.tsx              # Layout primitive (max-w, padding)
```

**Styling conventions:**

- Tailwind CSS 4 utility-first, no CSS modules.
- shadcn/ui for `Button`, `Input`, and any card primitives. Install components (`npx shadcn-ui@latest add button input`) in the same PR.
- No custom theme colours beyond what `tailwind.config` exposes — keep the page neutral/slate-toned, citation-tooltip accent optional.
- Responsive: mobile-first. Hero stacks vertically on mobile, side-by-side on md+.
- Reduce motion friendliness: `prefers-reduced-motion` respected — the looping demo GIF should pause if the user requests it.

**Email capture component (`EmailCaptureForm.tsx`):**

- Controlled component, React state only (no react-hook-form — the existing codebase uses plain controlled inputs per `frontend/CLAUDE.md`).
- Fields: `email` (required, regex-validated client-side), `consent` (required checkbox).
- Submit calls `api/beta.ts::requestBetaAccess({ email, source, consented })`. `api/beta.ts` is a new file — add it alongside existing `api/analyses.ts` / `api/profiles.ts`.
- Fires `landing_email_submit_attempt` / `_success` / `_error` to PostHog.
- Success state: inline confirmation, form replaced with *"Thanks — invite coming within a few days."*
- Error state: show `{error.message}` from the API response per the existing pattern.

**Backend endpoint (FastAPI):**

- `POST /api/v1/beta/requests` — validates email + consent, inserts row into `beta_requests`.
- Rate limit: 5 requests per IP per hour to prevent spam (reuse existing middleware if present).
- No authentication required (anonymous POST).
- Returns `{ id, email }` on success.
- Alembic migration 008 adds `beta_requests` table. Use `spelix-migration` agent to generate and apply.
- Admin endpoint `POST /api/v1/admin/beta/requests/{id}/approve` — auth-gated, generates invite token, sends email. Can ship in a follow-up PR — V1 can accept approvals done manually via SQL for the first week.

**`public/beta-terms.md` content (separate file, drafted in same PR):**

Two paragraphs, per `STRATEGY.md` v3 Day 1-2:

1. **Beta status + purpose:** Spelix is in private beta. Feedback is educational/performance only, not medical or clinical, not a substitute for a qualified coach or medical professional.
2. **Data, retention, rights:** What is collected (video → skeleton data only, deleted video, retained metrics). User rights (export, delete, withdraw). Age 18+. Contact for deletion requests.

Rendered at `/beta-terms` via `react-markdown`.

**Accessibility (WCAG 2.1 AA, in line with existing Spelix standards):**

- Semantic HTML landmarks (`<header>`, `<main>`, `<section>`, `<footer>`).
- Hero heading = `<h1>`. Each section = `<h2>`. No heading level skips.
- All images: meaningful `alt` text (hero screenshot alt = "Results page showing streaming coaching with a citation tooltip" etc).
- Colour contrast ≥ 4.5:1 for body text.
- Form inputs have associated labels (not placeholder-only).
- CTA buttons announce status changes via ARIA live regions on form submission.

**Testing:**

- Vitest + React Testing Library for the new components. Coverage target 90% per existing frontend standard.
- Tests must cover: auth-redirect behaviour on `/`, email validation, consent-required state (`aria-disabled`), successful submit path, error path (mock 4xx response), section rendering with correct headings.
- Playwright MCP E2E on spelix.app after merge: navigate to `/`, scroll through each section, submit a test email, confirm the thanks state, check console for errors, check network for 4xx/5xx.
- Do not connect to real Supabase in unit tests — mock `@/lib/supabase` per the existing pattern in `frontend/CLAUDE.md`.

**Merge gate (per `CLAUDE.md` Checkpoint Workflow):**

- Feature branch `feat/landing-page-v1`.
- Green CI: ruff + pyright (backend migration) + tsc + vitest + playwright smoke.
- PR via `mcp__github__create_pull_request`.
- Merge via `mcp__github__merge_pull_request` with `merge_method: "merge"` (never squash).
- Wait for "Deploy to Production" step.
- Playwright MCP E2E verification on live spelix.app after deploy.

---

## 11. Acceptance Checklist

Before V1 ships on Apr 15 (end of Day 2), every item below must be true.

**Content:**
- [ ] Every section has final-draft copy, edited by founder
- [ ] Hero screenshot is a real capture from live spelix.app, retina quality
- [ ] No prohibited language anywhere (see §3.1) — verified by grep: `rg -i "injury|safety score|medical advice|diagnos|revolutionary|95% accurate" frontend/src/components/landing frontend/public/beta-terms.md`
- [ ] Mandatory disclaimer appears below hero CTA AND in page footer, verbatim
- [ ] Kinesiology credential string is verbatim per SRS §829
- [ ] JMIR 8% citation includes year (2024) — no further citation detail required on the page itself but founder should have the DOI on hand for any Reddit / recruiter who asks

**Technical:**
- [ ] `/` route serves `LandingPage` to anonymous visitors, redirects to `/upload` for authenticated
- [ ] `/beta-terms` renders `public/beta-terms.md`
- [ ] Email capture POSTs to `/api/v1/beta/requests` and inserts into `beta_requests`
- [ ] Alembic migration 008 applied, `beta_requests` table exists with RLS
- [ ] PostHog events fire for `landing_view`, `landing_email_submit_attempt`, `landing_email_submit_success`
- [ ] All Vitest tests green, coverage ≥ 90% on new components
- [ ] Playwright E2E on spelix.app passes after deploy: navigate → scroll all sections → submit email → see thanks state → no console errors

**Compliance:**
- [ ] Consent checkbox required on both email forms; submit blocked until checked
- [ ] `public/beta-terms.md` exists and renders correctly
- [ ] Disclaimer appears in `AppLayout` footer on all authenticated routes too
- [ ] No references to source repo, no named third-party libraries in user-facing copy

**Strategy:**
- [ ] Under 6 hours of total dev time for V1 (budget check against `STRATEGY.md`)
- [ ] ONE_PAGER.md exists and cross-links to the landing page
- [ ] Landing page URL is suitable to drop into a Reddit post (no auth-gate, no cookie banner walls)

---

## 12. Open Decisions

Items requiring founder input before implementation starts. None of these blocks the plan — they are judgment calls the founder should make rather than the implementer guessing.

**D-1. Hero headline variant.**
Recommendation: Option A (citation-forward). Alternatives in §4.

**D-2. Whether to show founder's name / photo anywhere on the landing page.**
Trade-off: personal touch earns trust in the warm-network phase. Cost: recruiters reading the page conflate it with a solo-founder product narrative, which helps or hurts depending on the role. Recommendation: show a small "Built by [founder name] in collaboration with a kinesiology-specialist B.Sc. candidate" byline in the footer only. Full profile on ONE_PAGER, not on spelix.app.

**D-3. Whether to cite Formcheck / AiKYNETIX / Tonal by name in Section 2.**
Draft says avoid — naming risks adversarial replies in the Reddit thread and reads defensive to recruiters. Recommendation: do not name. SRS competitive analysis (§437) can inform founder answers in comments but does not need to appear on the page.

**D-4. Which existing beta user (if any) will be quoted in V2 Section 8.**
Depends on Sprint BETA (May 4-14) in-person / remote sessions producing a clean quote. Recommendation: pencil in placeholder for V2, upgrade only if an early beta user offers a usable sentence.

**D-5. Whether to offer a demo video without requiring signup.**
Trade-off: higher-quality top-of-funnel, but the main product demo is the real signup hook. Recommendation: embed the 20-30 sec demo GIF in Section 3 (V2), not as a gated asset.

**D-6. Whether the Coach Brain concept visual should be a static SVG or a small animation.**
Animation adds polish. Static SVG ships faster. Recommendation: static for V1, animation for V2 if time permits. Lottie if animated.

**D-7. Favicon / browser title bar.**
Current `favicon.svg` and `<title>` need to be reviewed. Recommendation: update `<title>` to *"Spelix — Barbell form coaching, grounded in research"* and keep existing favicon unless the wordmark is redesigned.

**D-8. Analytics consent banner.**
PostHog with cookie-based identification under GDPR requires consent. Recommendation: use PostHog's cookieless / IP-free configuration to avoid the banner entirely. Document this choice in a new ADR (`decisions.md`).

---

## 13. Deltas From Initial Draft

A focused list of what the refined plan changes from the Claude chat draft, with reasons. Each delta traceable to a constraint in §1 / §3.

| # | Draft said | Plan says | Reason |
|---|------------|-----------|--------|
| Δ1 | "a certified kinesiology collaborator" | "a kinesiology-qualified B.Sc. candidate" / SRS §829 verbatim credit line | Expert is Year 3 Pre-Med, not certified. Overstatement is FTC-exposed and SRS-prohibited. |
| Δ2 | "stress on your joints that compound over time" (Movement Quality) | "movement patterns that affect long-term joint health and loading quality" | Avoids injury-adjacent framing. SaMD/FTC compliance. |
| Δ3 | "Control is where fatigue shows up before form breaks down" | "Control is where fatigue becomes visible before form changes meaningfully" | "Breaks down" reads quasi-clinical; softer phrasing stays in wellness framing. |
| Δ4 | "early warning signal in your training" | "earliest signal in your training" | Removes "warning" — clinical tone. |
| Δ5 | 9 sections all shipping at once | 8 sections, V1/V2 split | Day 1-2 is shared with expert PDF upload wiring as a parallel hard gate; V1 must be minimum viable to hit Apr 15, with V2 polish rolling into Sprint BETA. |
| Δ6 | "5-tier confidence" marketed as a differentiator | Categorical confidence (High/Moderate/Low/Very Low) shown implicitly via screenshot; "5-tier" kept for the technical blog | User-facing confidence is 4 categorical per FR-CVPL-25; "5-tier" is internal terminology. |
| Δ7 | Coach Brain framed as a current continuously-compounding system | Coach Brain framed as a coaching intelligence layer that compounds with analysis volume — kept as present-tense differentiator per founder direction (Phase 3 distillation ships in coming weeks) | Founder confirmed Phase 3 is near-term; draft language works. |
| Δ8 | Mandatory disclaimer text implied, not quoted | Disclaimer quoted verbatim from SRS §265, appears below hero CTA + in site-wide footer | NFR-USAB-06 and SRS §265 require verbatim language. |
| Δ9 | Signup implied as self-serve | Explicit email capture → manual approval → invite-token signup flow (§7) | Matches `STRATEGY.md` v3 Day 1-2 plan. Manual approval continues through Sprint BETA (May 4-14); no auto-gate planned for L3 or L4 in v3. |
| Δ10 | No instrumentation spec | Full PostHog event schema (§8) | STRATEGY.md v3 Day 1-2 requirement. |
| Δ11 | "Private beta users matter" section (draft Section 7) as its own section | Merged into §6.8 Final CTA ("What beta users get" bullets) | Tighter. Saves word count for V1 ship. |
| Δ12 | "Loom walkthrough" / blog-post cross-links mentioned in strategy but not in draft | Deferred to V2 once those artefacts exist (Sprint BETA May 4-14 / Sprint GROW May 15-Jul 1 per `STRATEGY.md` v3) | Avoid linking to placeholders. |
| Δ13 | No mention of consent checkbox on email capture | Required consent checkbox on both forms; `aria-disabled=true` pattern (matches `UploadPage`) | GDPR + `STRATEGY.md` v3 Day 1-2 disclaimer requirement. |
| Δ14 | Draft doesn't address auth redirect | Landing preserves existing `HomePage.tsx` behaviour: authed users redirect to `/upload` | Keeps login UX intact; avoids regression for beta users returning. |
| Δ15 | No GDPR / DPIA mention | §6.7 covers data retention, not-a-medical-device, and data ownership in plain language | SRS NFR-PRIV-01 through -07, GDPR Article 35. |
| Δ16 | Draft names no specific page architecture file / component structure | §10 specifies component file tree, new routes, new API endpoint, new migration | Required for implementation to start. |
| Δ17 | Draft mentions "our expert" language | Forbidden; verbatim SRS §829 string is the only permitted credit line | SRS hard rule. |

---

## 14. Out Of Scope

Explicitly deferred from this plan. Not because they are unimportant — because they belong in a different work item.

- **ONE_PAGER.md drafting** — tracked separately in `STRATEGY.md` v3 Privacy surface area; not a Day 1-2 blocker.
- **Architecture diagram** (`docs/architecture.png`) — tracked separately; not a Day 1-2 blocker.
- **Demo GIF recording** — not a Day 1-2 task in STRATEGY.md v3; landing wires it in V2 if/when recorded.
- **Blog post writing** — STRATEGY.md v3 §Blog Plan: posts 1-2 target May 4-14 (Sprint BETA), posts 3-5 target Jun 1 - Jul 1 (Sprint GROW). Landing cross-links added in a follow-up PR.
- **Loom walkthrough** — tracked separately in STRATEGY.md v3 §Privacy Policy (public surface area).
- **Admin approval UI** for `beta_requests` — ships in follow-up PR. Day 1-2 founder can approve via raw SQL or Supabase dashboard; Sprint BETA rolls batches of 5.
- **Automated invite email sending** — can be manual in the first few days of beta. Transactional email provider selection is a separate decision.
- **Anonymous landing A/B testing** — not in scope until user volume supports it (L3 2026-05-15 at earliest).
- **Copy translation / internationalisation** — English only through L3.
- **SEO optimisation beyond basic meta tags** — post-L2 task.
- **Replacing the existing HomePage auth-redirect** with anything more sophisticated than `useEffect` check — deferred to auth-flow refactor if ever needed.

---

## 15. Next Steps After Founder Approval

1. Founder reviews this plan, edits copy and decisions in-place, marks Section 11 items accepted.
2. Invoke `writing-plans` skill to generate a step-by-step implementation plan (feature branch, migration, component scaffolding, TDD gates, PR/merge sequence).
3. Execute the implementation plan — default to `spelix-tdd` for components + tests, `spelix-migration` for the migration, `spelix-security-reviewer` before merge.
4. Merge to main, wait for CI "Deploy to Production," run Playwright MCP E2E verification.
5. Add ADR to `decisions.md` recording the landing-page architecture choices (analytics consent approach, manual approval flow, V1/V2 split).
6. Update `backlog.md` with L2-LANDING-01 through L2-LANDING-0N task entries and mark them `done` with the merge commit SHA.

---

## 16. Template Replication Plan — Framer "EvoTrack" → Spelix Landing V1

**Added:** 2026-04-15 (Day 2 of L2 sprint) by Atharva. Extends the generic plan (§§1–15) with the concrete template we are copying from, the exact design tokens extracted from it, and the mapping of every template surface onto Spelix content. Read §§1–3 and §6 first — this section assumes those constraints as non-negotiable.

### 16.1 Template & Provenance

- **Live reference:** https://fluid-actor-392760.framer.app/ ("EvoTrack – AI & Smart Tech Landing Page Template", Framer, exported 2026-04-13 by NoCodeExport)
- **Local export:** `landing-page/template-export/index.html` (435 KB, hotlinks Framer CDN assets — open with internet access)
- **Screenshots (desktop @ 1440, responsive-mobile @ 375, responsive-tablet @ 768):** `landing-page/screenshots/`
  - `01-desktop-full.png` — full scrollable page
  - `02-hero.png` through `08-final-cta-footer.png` — 7 viewport captures top to bottom
  - `responsive-mobile.png`, `responsive-tablet.png`, `responsive-desktop.png`
- **Accessibility tree:** `landing-page/screenshots/tree-desktop.txt`
- **Raw token introspection JSON:** `landing-page/design-tokens.json`, `landing-page/structure.json`
- **Extract scripts (re-runnable against the live URL):** `landing-page/extract-tokens.js`, `landing-page/extract-structure.js`

**Why this template.** The template reads as a "quiet-confident tech-product" landing — dark photo hero, generous whitespace, light body surfaces, one distinctive accent colour, large light-weight headlines, section labels above each H2, card grids + one accordion + one testimonial carousel + one final CTA block. That matches the Cronometer-ish tone §1 calls for far better than a generic SaaS gradient template. Zero section here is wasted on Spelix.

**Scope of copying.** Everything visual — colours, typography scale, spacing rhythm, radii, section layouts, scroll-reveal motion, component primitives (accordion, pill CTA, section-label, card grid, rounded-dark-CTA-block). Everything textual is **100% replaced** with Spelix content from §§4–6. No template copy survives.

### 16.2 Design Tokens — Exact Values From Live CSS

Extracted from `getComputedStyle` on the live template, 2026-04-15. These are the authoritative values — commit them into `tailwind.config.ts` / `globals.css` exactly.

**Colour palette.**

| Role | Token | Value | Notes |
|---|---|---|---|
| `--brand-primary` | chartreuse / lime-green | `#D5FF45` (rgb 213 255 69) | CTA button fill; hero accent badges; accordion-open marker |
| `--brand-primary-soft` | pale chartreuse | `#E8FF9C` (rgb 232 255 156) | Hover state on primary; inactive pill fill |
| `--brand-primary-glow` | chartreuse 20% | `rgba(213, 255, 69, 0.2)` | CTA box-shadow on hover/focus |
| `--surface-page` | page background | `#FAFAFA` (rgb 250 250 250) | Body bg between sections |
| `--surface-elevated` | white | `#FFFFFF` | Cards on light bg |
| `--surface-dark` | near-black | `#121212` (rgb 18 18 18) | Dark product cards (AI in Action carousel), final CTA panel |
| `--ink-primary` | black | `#000000` | Body text on light surfaces |
| `--ink-on-dark` | white | `#FFFFFF` | Body text on dark surfaces |
| `--ink-muted` | 70% dark gray | `rgba(48, 48, 48, 0.7)` | Section labels ("Introduction", "AI in Action", etc.), secondary meta text |
| `--ink-on-dark-muted` | 80% near-white | `rgba(235, 235, 235, 1.0)` | Nav links on hero photo |
| `--border-subtle` | black 16% | `rgba(0, 0, 0, 0.16)` | Accordion item dividers; card hairlines |
| `--divider-soft` | gray 15% | `rgba(187, 187, 187, 0.15)` | Footer divider; faint grid lines |

**One colour-philosophy note** — the template's chartreuse is loud. Spelix's §2 persona ("evidence-forward, calm, Cronometer-style") can absolutely carry one loud accent so long as the rest of the page is quiet, which the template already enforces. **Keep the chartreuse verbatim as Spelix's marketing accent.** Rationale: (a) we need a distinctive brand colour that the product UI doesn't already use (product uses neutral slate + blue-ish status colours), (b) chartreuse is unusual enough to not feel generic-SaaS, (c) it signals "scientific/analytical" more than a blue or purple would. If the founder rejects the colour, the swap is one token line — design system is additive, not coupled.

**Typography.**

| Role | Font | Weight | Size | Line-height | Letter-spacing | Colour |
|---|---|---|---|---|---|---|
| Hero H1 | `Host Grotesk` | 400 | 56px | 56px (1.0) | -1.68px (-0.03em) | `--ink-on-dark` |
| Section H2 (on light) | `Host Grotesk` | 400 | 40px | 44px (1.1) | -1.2px (-0.03em) | `--ink-primary` |
| Card title H2/H3 (on dark card) | `DM Sans` | 500 | 20px | 22px (1.1) | -0.6px (-0.03em) | `--ink-on-dark` |
| Section label (above H2) | `DM Sans` | 400 | 14px | 18.2px (1.3) | normal | `--ink-muted` |
| Nav link | `DM Sans` | 400 | 16px | 20.8px (1.3) | normal | `--ink-on-dark-muted` |
| Body paragraph | `DM Sans` | 400 | 16px | ~1.5 | normal | `--ink-primary` |
| Small meta / byline | `DM Sans` | 400 | 14px | 1.3 | normal | `--ink-muted` |

**Mobile scale-down (from responsive screenshots):** H1 ~36px / H2 ~28px / body unchanged. Exact breakpoints follow Tailwind defaults (`md: 768px`, `lg: 1024px`).

**Font loading.** Both fonts are on Google Fonts — no need to host locally. Add to `frontend/index.html` `<head>`:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,wght@0,400;0,500;1,400&family=Host+Grotesk:wght@400&display=swap" rel="stylesheet">
```

Preload only the weights we use. `font-display: swap` prevents FOIT.

**Spacing & rhythm.**

- **Section vertical padding**: `py-24` (96px top + 96px bottom — confirmed on 6 of 7 sections)
- **Footer/CTA band padding**: `py-12` (48px top + 48px bottom)
- **Container max-width**: `max-w-[1128px]` (1128px — Framer's chosen content width; use a CSS custom prop so we can tune once)
- **Horizontal gutter**: responsive — `px-6` mobile / `px-12` tablet / `px-16` desktop (extrapolated from screenshot inspection)

**Border radii.**

| Radius | Use |
|---|---|
| `6px` | Small chips / tags |
| `8px` | Pill nav button (secondary) |
| `12px` | Primary CTA button ("Join waitlist now") — **authoritative** |
| `16px` | Small product cards |
| `20–24px` | Medium cards (accordion items, testimonial quote cards) |
| `40px` | Large cards (AI in Action carousel cards, hero-embedded figure) |
| `100px` | Pill shape (nav CTA, small badges) — use `rounded-full` |
| `50%` | Circle (icon containers, slideshow nav arrows) — use `rounded-full` |

### 16.3 Section-by-Section Mapping — Template → Spelix

Each row: template section → Spelix plan section → V1 inclusion → notes on what changes.

| # | Template section | Spelix plan section | V1? | Key adaptation |
|---|---|---|---|---|
| A | Nav bar (logo + 4 links + Join CTA) | new — not in plan | V1 | Replace "EvoTrack + 4 links" → "Spelix + 3 links (How it works, Why Spelix, Privacy)". CTA stays as "Request beta access" anchor-link to `#final-cta`. Sticky on scroll. |
| B | Hero (photo bg + H1 + subhead + CTA pill) | §6.1 | V1 | Swap bg image (see §16.4). H1 = Option A from §4. CTA = email input inline + "Request private-beta access" button. Disclaimer badge below CTA per §6.1. |
| C | "Introduction / Smarter. Faster. More Personal." — big stat + 3 bullets | §6.2 Problem | V1 | Big stat becomes **"8%"** + caption "of AI fitness apps cite their sources (JMIR, 2024)". Three bullet leads → "No source / No consistency / One body fits all" failure modes verbatim from §6.2. |
| D | "AI in Action / Your AI coach, always on your wrist" — horizontal card carousel of 6 feature pills | §6.3 How Spelix Works | V1 | **Use non-scrolling 3-card grid**, not the 6-card carousel (overkill + we only have 3 steps). Cards: Upload / Analyse / Coach-with-citations. Below the grid: "What you get" bullets (§6.3). |
| E | "Why It Works / Smarter training with clear and proven results" — 5-item accordion on left + product image right | §6.4 Differentiators | V1 | **Perfect fit.** Accordion on left = 3 items (not 5): Every claim cites its source / Built with a kinesiology specialist / The Coach Brain compounds. Image on right = Spelix ResultsPage with citation tooltip expanded (§9 asset #1). First item open by default. |
| F | "Testimonials / Trusted by Athletes Worldwide" | — (skipped for V1) | — | Cut from V1. No beta users to quote yet. Add to V2 per §5 once Sprint BETA produces a clean quote. Keep template pattern noted for the re-add. |
| G | "FAQ / Frequently Asked Questions" — 6-item accordion | **repurpose** → §6.7 Privacy & Disclaimer | V1 | **Reskin as Privacy**. Headline "What Spelix does with your video — and what it does not do." 3 accordion items (not 6) matching §6.7 exactly: "Your video is not kept" / "Spelix is not a medical device" / "Your data belongs to you". |
| H | Final CTA (dark rounded block w/ email input + button) | §6.8 Final CTA | V1 | Copy layout verbatim. Swap text to §6.8: "You have filmed your lifts..." + consent checkbox + email input + "Join the private beta". Final disclaimer line below. |
| I | Footer (logo + tagline + social + nav) | not in plan | V1 | Minimal: Spelix wordmark + §3.2 disclaimer (always visible) + 2 nav links (`/beta-terms`, future `/privacy`) + byline (§12 D-2 recommends a small "Built by [name] with a kinesiology-specialist B.Sc. candidate"). No social icons for V1 (no live channels yet). |
| — | — | §6.5 Four Dimensions | **V2 only** | Shown in plan §5 as V2. When added, use a 2×2 card grid reusing the `Card` primitive from Section D. |
| — | — | §6.6 Roadmap | **V2 only** | Same. 3-card row using Section D primitive, but with simple icons instead of photos. |

### 16.4 Visual Assets — Template Uses vs What We Swap

The template hotlinks 25 images + 7 background images from `framerusercontent.com`. Spelix cannot use any of them (licence, domain hotlink fragility, off-topic imagery). Map per-surface:

| Surface | Template uses | Spelix uses | Provenance |
|---|---|---|---|
| Hero background | Dark-blue photo of woman on rooftop lifting arms (framerusercontent.com) | **A single high-fidelity dark photo of a barbell lift** — sagittal view, low-saturation, high contrast. Sourced from a paid stock library (Unsplash pro / Pexels) OR the founder's own gym footage treated to match. Must be NON-gendered-focal (no faces as the dominant feature). Store at `frontend/public/landing/hero-bg.webp` — WebP, progressive, ≤250 KB, 2560×1600 source, CSS `object-fit: cover`. | §9 asset list + new |
| Hero foreground focal element | Smartwatch product mockup with "00" dial | **Spelix ResultsPage hero crop** — small floating "product" card showing a coaching paragraph mid-stream with one citation tooltip expanded. This becomes the single visual proof point. Capture via Playwright MCP on spelix.app against a real completed analysis; crop to ~480×640. | §9 asset #1 (already in plan) |
| Intro "25%" stat section | (no image) | **No image** — just the big 8% + caption. Keep section minimal, text-only. | n/a |
| "AI in Action" 6 carousel cards | 6 dark product-scene photos + smartwatch crops | **3 step illustrations** — each a small schematic + label: (1) phone-with-video icon, (2) pose-skeleton overlay icon/SVG, (3) citation-tooltip mockup icon. Option to replace the third card photo with the actual `citation-tooltip.png` crop from §9. | §9 asset list |
| "Why It Works" accordion+visual | Landscape hillside photo w/ floating watch stats | **Spelix ResultsPage full screenshot** (hero screenshot from §9 asset #1 reused) — fills the right column. First accordion item open ("Every claim has a source") so the visual reinforces citation presence. | §9 asset #1 reused |
| Final CTA rounded block | Dark photo of woman running | **Reuse hero bg crop** or a different frame from the same source video/photo. Keep it dark enough that white text + chartreuse CTA button both read at AA contrast. | derivative of hero bg |
| Footer | — | — | n/a |

**Asset production order for V1:**

1. Hero background image (founder picks a stock image or provides own shot → crop/compress).
2. ResultsPage hero screenshot via Playwright MCP against spelix.app (real analysis, citation tooltip expanded).
3. Three step icons — SVG, ~96×96, monochrome stroke at `--ink-primary`, optional `--brand-primary` fill for the current step.
4. Citation tooltip crop — from the same screenshot #2, zoomed detail saved separately for Section D card 3.

**Budget:** all 4 assets should take ≤ 60 min combined. No custom illustration needed for V1.

### 16.5 Component Architecture — Additions to §10 Tree

§10 already specifies `src/components/landing/*`. Template adaptation adds these primitives (all in the same folder):

```
src/components/landing/
  SectionLabel.tsx          # Uppercase-ish 14px DM Sans label with tiny diamond icon ◆ on the left
  SectionHeading.tsx        # H2 wrapper with the 40px / 44lh / -1.2px tracking
  StatCard.tsx              # Big-number "8%" display — Section C
  StepCard.tsx              # One of the 3 "How it works" cards — Section D
  DifferentiatorAccordion.tsx  # The left-side accordion list — Section E
  AccordionItem.tsx         # Single expandable item used by DifferentiatorAccordion + PrivacyAccordion
  PrivacyAccordion.tsx      # Reuses AccordionItem — Section G
  NavBar.tsx                # Sticky top nav on hero + light version on scroll
  Footer.tsx                # Dark-on-light footer row
  ScrollReveal.tsx          # IntersectionObserver + Web Animations API wrapper (see §16.7)
```

**Primitive reuse rules:**
- `EmailCaptureForm` (already in §10) is used in both Hero and FinalCta. Don't duplicate.
- `AccordionItem` is used in both Differentiators (Section E, 3 items) and Privacy (Section G, 3 items). Keep it styled once.
- `SectionLabel` is used at the top of every section except Hero — centralise the "◆ Introduction" pattern so we don't duplicate CSS.

**No carousel primitive for V1.** Section F (Testimonials) is skipped; Section D uses a non-scrolling grid. Defer Embla/keen-slider install to V2.

### 16.6 Tailwind v4 Config Additions

Tailwind 4 uses `@theme` in `globals.css` for tokens. Add (or merge into existing):

```css
/* frontend/src/styles/globals.css */
@theme {
  /* Brand — landing page */
  --color-brand-primary:       #d5ff45;
  --color-brand-primary-soft:  #e8ff9c;
  --color-brand-primary-glow:  rgba(213, 255, 69, 0.2);
  --color-surface-page:        #fafafa;
  --color-surface-dark:        #121212;
  --color-ink-primary:         #000000;
  --color-ink-muted:           rgba(48, 48, 48, 0.7);
  --color-ink-on-dark:         #ffffff;
  --color-ink-on-dark-muted:   #ebebeb;
  --color-border-subtle:       rgba(0, 0, 0, 0.16);

  /* Typography — landing page */
  --font-display:  "Host Grotesk", ui-sans-serif, system-ui, sans-serif;
  --font-sans:     "DM Sans", ui-sans-serif, system-ui, sans-serif;

  /* Landing container width */
  --container-landing: 1128px;
}
```

Usage in JSX: `className="bg-[var(--color-brand-primary)] text-[var(--color-ink-primary)] font-[var(--font-display)]"` OR (cleaner) extend Tailwind's shorthand with arbitrary values: `bg-brand-primary`, `font-display`. Tailwind 4 auto-exposes `@theme` vars to the `-*` utility shorthand.

**Existing app colour tokens stay untouched** — product routes (`/upload`, `/results/:id`, `/history`) keep the existing slate/blue palette. Only `LandingPage` + `BetaTermsPage` consume the brand tokens. Concretely: do not globalise `--color-brand-primary` into shadcn `Button` variants — use it as an explicit `className` override on landing components only.

### 16.7 Motion & Scroll Reveal

Template uses **vanilla IntersectionObserver + Web Animations API** (seen in `template-export/index.html` lines 320–489):

- Duration: **600ms**
- Easing: **ease-out**
- Initial: `opacity: 0; transform: translateY(20px)` (fallback when data-attr not set)
- Final: `opacity: 1; transform: none`
- Fill mode: `forwards`
- Respects `prefers-reduced-motion: reduce` → skips animation, sets final styles immediately

**Implementation for Spelix**: a lean `ScrollReveal.tsx` hook + wrapper. Zero animation library dependency.

```tsx
// frontend/src/components/landing/ScrollReveal.tsx (sketch — do not copy verbatim)
export function ScrollReveal({ children, delay = 0, translateY = 20 }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduce) { el.style.opacity = '1'; return; }
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (!e.isIntersecting) return;
        e.target.animate(
          [
            { opacity: 0, transform: `translateY(${translateY}px)` },
            { opacity: 1, transform: 'translateY(0)' },
          ],
          { duration: 600, delay, easing: 'ease-out', fill: 'forwards' },
        );
        io.unobserve(e.target);
      });
    }, { threshold: 0.15 });
    io.observe(el);
    return () => io.disconnect();
  }, [delay, translateY]);
  return <div ref={ref} style={{ opacity: 0 }}>{children}</div>;
}
```

**Where to apply**: wrap each major section's heading + first-paragraph block + each card. Stagger by 100–200ms between sibling cards for the classic "rolling in" feel. Do NOT wrap the hero — it's above the fold and must be visible instantly.

**Hero-specific motion**: the template uses a subtle scale-in on the hero headline. Add optional `.animate-hero-in` class (500ms fade + 1.02→1.0 scale, 200ms delay after mount) — applied once with CSS `@starting-style` (Tailwind 4 / modern browsers) with a JS fallback that just sets final values on browsers without support.

### 16.8 Forbidden-Language Remapping — Template Violates §3.1

The template contains these strings we **must not copy**. Replacements come from §3.1 / §§6.x:

| Template string | Lands where | Spelix replacement |
|---|---|---|
| "Injury Prevention" (§4 card #3 title) | AI in Action carousel card | **Never use.** Not applicable anyway — we're replacing the whole carousel with 3-step How-It-Works. No card on injury. |
| "at risk" / "risky movements" (card description) | AI in Action card body | **Never use.** Same — whole card goes away. |
| "Proven Accuracy" / "medical-grade sensors" / "ensures highly accurate data" (FAQ answer) | FAQ accordion | **Never use.** FAQ repurposed to Privacy — none of these phrases carry over. |
| "95%" / specific accuracy numbers | (template FAQ wording implies precision) | **Never use.** §3.1 explicit ban on unverified accuracy claims. |
| "the future of fitness", "next-gen", "revolutionary" | (none on this template, checked) | — |
| "Push Your Limits with AI Precision" (hero H1) | Hero | Replace verbatim with §6.1 Option A: *"Barbell form coaching where every piece of feedback cites its source."* |
| "Track every move, analyze your performance, and get real-time coaching, all from your wrist." (hero subhead) | Hero | Replace with §6.1 subhead about CV + peer-reviewed lit. |
| "Join waitlist" / "Join the waitlist" (CTA button label) | Nav + Hero + Final CTA | Replace with **"Request private-beta access"** (hero) / **"Join the private beta"** (final CTA) per §6.1 / §6.8. Avoid "waitlist" — sounds commercial; Spelix is private beta. |
| "Created by Arthur in Framer" | Footer byline | Replace with §12 D-2 recommended byline. Drop the "in Framer" credit. |

**Greptest before merge:** run this command and expect zero matches in the landing components:

```bash
rg -i 'injur|safety score|medical advice|diagnos|revolutionary|next-gen|future of fitness|95% accurate|proven accuracy|medical-grade|waitlist' frontend/src/pages/LandingPage.tsx frontend/src/components/landing/ frontend/public/beta-terms.md frontend/public/landing/
```

### 16.9 Implementation Task Order — Next Prompt

Exact order. Each step is a TDD gate or a reviewable commit. Matches the §10 spec + the template additions above.

1. **Tailwind theme tokens** (`globals.css`): add `@theme` block from §16.6. Commit.
2. **Google Fonts link** in `frontend/index.html`: Host Grotesk 400 + DM Sans 400/500. Commit.
3. **Primitives first, in order** — no tests on pure layout wrappers; Vitest on anything with state or conditionals:
   - `SectionWrapper.tsx`, `SectionLabel.tsx`, `SectionHeading.tsx` → commit together
   - `ScrollReveal.tsx` + unit test (reduced-motion branch, IO trigger) → commit
   - `AccordionItem.tsx` + unit test (expand/collapse, keyboard `Enter`/`Space`, ARIA `aria-expanded`) → commit
   - `EmailCaptureForm.tsx` + unit tests from §10 (validate email, consent required, success state, error state) → commit
4. **`api/beta.ts`** — thin client for `POST /api/v1/beta/requests`. Mock in tests. Commit.
5. **Backend: `POST /api/v1/beta/requests`** — FastAPI router, rate-limited, email+consent validation, INSERTs into `beta_requests` (migration 008 already live). Pydantic schema + repo layer + unit test + integration test. Commit.
6. **Section components in page order** — Hero, Problem (stat + 3 failure modes), HowItWorks (3 step cards), Differentiators (accordion + image), Privacy (accordion), FinalCta, Footer, NavBar. Each gets a snapshot test asserting the heading + any dynamic regions render. Commit per section.
7. **Assemble `LandingPage.tsx`** — wire section composition, preserve existing auth-redirect behaviour (check `supabase.auth.getSession()` → redirect to `/upload`). Commit.
8. **`BetaTermsPage.tsx` + `public/beta-terms.md`** — add `react-markdown` dep, render file. Commit.
9. **Route swap** in `src/routes.tsx`: `/` → `LandingPage`, add `/beta-terms`. Commit.
10. **Assets** — copy hero bg, ResultsPage screenshot, citation tooltip crop, 3 step icons into `frontend/public/landing/`. Commit.
11. **PostHog instrumentation** — `landing_view`, `landing_email_submit_attempt/_success/_error`, `landing_beta_terms_click`, `landing_scroll_depth` (IO-based per §8). Config uses cookieless mode per §12 D-8. Commit.
12. **Full vitest run + coverage check** ≥ 90% on new components. Commit if anything added.
13. **Grep gate** per §16.8. If it finds anything, fix in-place. Commit.
14. **Manual run** — `cd frontend && npm run dev`, walk Hero → Problem → HowItWorks → Differentiators (expand each accordion item) → Privacy (expand each) → FinalCta → submit test email → confirm thanks state. Screenshot each for self-QA into `landing-page/screenshots/built-v1-*.png`.
15. **Open PR** `feat/landing-v1` → `main`. Include migration 008 reference (already merged). Security review request on `spelix-security-reviewer` for auth-adjacent surfaces (consent language, disclaimer presence).
16. **After merge + Deploy to Production** — Playwright MCP E2E on live spelix.app per §10 merge-gate block. Record verification into the handoff.

**Budget guardrail** (§11 strategy item): V1 total dev time under 6 hours. Template-based means most UI is assembly, not design. If any single task above exceeds 45 min, stop and ask.

### 16.10 Template Reference Cleanup Before Merge

The `landing-page/` folder exists for this sprint's work only. Decide at merge time:

- `landing-page/screenshots/*.png` — **keep** if we want them as a v1-handoff artefact; otherwise gitignore and leave on the branch. Recommendation: keep until Sprint BETA closes (May 14), then delete.
- `landing-page/template-export/index.html` — **delete before merge**. Licence uncertain (Framer template, free tier), 435 KB on main is unjustified once implementation is done.
- `landing-page/design-tokens.json`, `landing-page/structure.json`, `landing-page/extract-*.js` — **keep** as historical reference. <10 KB total. Useful if we re-theme.
- `landing-page/landing-page-plan.md` — **keep**. This becomes the V2 roadmap driver.

---

**End of template replication plan. Next prompt: begin implementation at §16.9 step 1.**
