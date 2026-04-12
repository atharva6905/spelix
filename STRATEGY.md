# Spelix Strategy — L2 Beta Launch + Fall 2026 Internship Plan

**Created:** 2026-04-11 | **Status:** ACTIVE | **Review date:** 2026-05-09 (end of L2 sprint)

---

## Priority Order (non-negotiable)

1. **Fall 2026 internship at a top AI lab** — Anthropic, OpenAI, Cohere, DeepMind, Meta FAIR, Google Research, xAI tier. This is the hard priority.
2. **Spelix as a real product** — serious long-term, but strictly subordinate to #1 until the internship is signed.
3. **Saturniq Summer 2026** — commitment already made, non-negotiable.

## Level Progression

| Level | Definition | Target Date | Time Budget |
|-------|-----------|-------------|-------------|
| **L1** (current) | Live URL, polished landing, no real users | Done | — |
| **L2** | Private beta, 20-50 free users, instrumented | **2026-05-09** | 15 hrs/week |
| **L3** | Open beta, organic growth, SEO, content | Summer 2026 (during Saturniq) | 5-8 hrs/week |
| **L4** | Commercial / paid / GTM | 2027 earliest | TBD |
| **L5** | Full startup | Explicitly off-table for 2026 | — |

## Privacy Policy

Source stays in private repo. Public surface area:

- **spelix.app** — live product demo (beta-gated)
- **spelix-public repo** (future) — README, `docs/decisions.md`, SRS excerpts, architecture diagrams, ONE_PAGER.md. Zero source code.
- **Blog posts** — technical deep-dives (5-tier confidence, stream-then-reparse, RAG eval). Public writing > public code.
- **Loom walkthrough** — narrated codebase tour, unlisted YouTube/Loom link.
- **Recruiter code access** — read-only GitHub collaborator invite to private repo, only when explicitly requested by a hiring manager. Revoke after interview cycle.

Reason: fast-follower clone defense + genuine product uniqueness, not paranoia.

## Stop-Loss Triggers

Revisit this strategy if any of these hit before September 2026:

- Paying customers appear unsolicited and won't go away
- Waitlist spikes past 1000 organically
- A top-AI lab explicitly says "pick between our offer and Spelix"
- Saturniq performance degrades because of Spelix time

---

## Phase 1: L2 Launch Sprint (4 weeks, Apr 11 - May 9)

### Week 1 — Foundations (Apr 11-18)

**Goal:** Ship interview-pack assets + prepare beta launch surface.

**Spelix (Track B, ~10 hrs):**

- [ ] Record 20-30s demo GIF: upload -> streaming coaching -> score cards. Commit to `docs/demo.gif`, wire into README.
- [ ] Excalidraw architecture diagram -> `docs/architecture.png`. Wire into README.
- [ ] 4 screenshots: upload page, results page with 4-dim cards + bar path, streaming coaching mid-flight, PDF report. Commit to `docs/screenshots/`.
- [ ] Write `docs/ONE_PAGER.md` — 1 page: problem, what it does, architecture sketch, metrics, status, contact.
- [ ] Landing page reframe: spelix.app hero flips from "I built this" to "Science-grounded AI form coaching — private beta for lifters." Email capture, beta disclaimer link, kinesiology-partner credit.
- [ ] Beta disclaimer + user agreement (2 paragraphs): not medical advice, not injury prevention, wellness tool for informational purposes, data retention (delete on request), age 18+. Commit to `public/beta-terms.md`, link from signup.
- [ ] Instrumentation: PostHog free tier or Plausible + custom `events` table in Supabase. Track: signup, first upload, upload completion, coaching view duration, thumbs up/down, PDF download, return visits.

**Internship (Track A, ~5 hrs):**

- [ ] Target list: 20-30 top-AI labs + Canadian bigtech. One row per company in `data/target-companies.md`: name, role(s), app open date, visa support, referral path.
- [ ] LeetCode: 5 mediums (3 + 2 across the week).
- [ ] Read 1 Anthropic/OpenAI technical blog post, write 3-paragraph reflection.
- [ ] Identify 5 alumni at target companies (LinkedIn + university alumni directory).
- [ ] Draft 2 of 5 STAR+R stories (150-200 words each) for `interview-prep/story-bank.md`.

### Week 2 — First 10 Users (Apr 18-25)

**Goal:** Get 10 real humans using Spelix. Sit behind them. Fix what breaks.

**Spelix (~12 hrs):**

- [ ] Warm network recruit: DM 10 people who lift (McMaster barbell club, gym friends, kinesiology partner's network). Script: "Built an AI form checker grounded in kinesiology research, free private beta, 5 min to upload a video, would love your feedback." Target: 4-5 signups.
- [ ] **In-person user session #1:** Sit physically next to a user while they upload. Do NOT help, explain, or demo. When they hesitate, write down why. When they do something unexpected, write down what. Write up as `docs/user-sessions/session-{date}-{initials}.md`.
- [ ] **In-person user session #2:** Different user, different lift if possible. Write up.
- [ ] Fix top 3 UX issues surfaced in sessions. Prioritize confusion over bugs.
- [ ] Second wave of DMs: 10 more warm-network lifters OR one small/trusted community (e.g., McMaster fitness Discord). Target: 5 more signups.
- [ ] **Weekly metrics review** (recurring, 30 min): signups, first-upload rate, thumbs, retention D1/D3/D7. Commit to `docs/metrics/2026-W17.md`.

**Internship (~5 hrs):**

- [ ] Draft 200-word LinkedIn DM template for alumni outreach.
- [ ] LeetCode: 5 mediums.
- [ ] Draft updated CV bullet for Spelix referencing real users: "Shipped to a private beta of N lifters, instrumented retention and coaching-quality metrics."
- [ ] Read one paper relevant to Spelix (RAGAS paper, keypoint pose estimation survey). Notes become interview talking points.
- [ ] Draft 2 more STAR+R stories.

### Week 3 — Scale to 30, First Public Signal (Apr 25 - May 2)

**Goal:** 25-40 total beta users, instrumented retention data, one public artifact.

**Spelix (~12 hrs):**

- [ ] Post in r/weightroom (NOT r/powerlifting yet). Rules: lead with the problem not the tech, cite the JMIR 8% statistic, explicit it's a free beta, link spelix.app, offer to answer technical questions. **Read subreddit rules first, respect self-promo policy, post once.** Expect 10-30 signups.
- [ ] Monitor Reddit post. Reply to EVERY comment in the first 24 hours, especially critical ones.
- [ ] Third user session: remote screen-share via Discord/Zoom if no local Reddit user. Watch, don't help.
- [ ] First blog post: "5-Tier Confidence: How Spelix Knows When It Doesn't Know." 800 words. Technical, specific, includes a screenshot of the breakdown for a real anonymized rep. Publish on spelix.app/blog or dev.to.
- [ ] Weekly metrics review. Add column: qualitative themes from user feedback. Commit to `docs/metrics/2026-W18.md`.
- [ ] **Loom walkthrough** (3-5 min): the problem -> pipeline -> 5-tier confidence -> stream-then-reparse trade-off -> Phase 2 RAG direction -> current beta numbers. Upload unlisted, link from spelix.app and ONE_PAGER.md.

**Internship (~5 hrs):**

- [ ] LeetCode: 5 mediums (or 3 mediums + 2 hards).
- [ ] Complete all 5 STAR+R stories in `interview-prep/story-bank.md`.
- [ ] Send 3 alumni LinkedIn DMs. Low volume, high signal, personalized each.
- [ ] 2 hours AI/ML fundamentals study: pick weakest topic (attention? backprop derivation? transformers? PPO? diffusion?).
- [ ] Draft application CV v1 tailored for AI/ML intern roles — Spelix + beta-user narrative as the lead.

### Week 4 — Lock L2, Saturniq Handoff (May 2-9)

**Goal:** Declare L2 done. Set up L3 autopilot. Shift gear toward internship prep.

**Spelix (~10 hrs):**

- [ ] **L2 completion audit:** instrumentation? 25+ users? retention data? user-session notes? at least 1 public artifact? coaching-quality metrics? If any missing — triage this week.
- [ ] Set up L3 auto-gate: beta signup stays invite-only but approval becomes automatic after email verify + disclaimer click.
- [ ] Write `docs/beta-runbook.md`: how to handle signup flood, what to do if droplet dies, rollback plan, kill-switch if legally weird things happen.
- [ ] Second blog post: "Stream-then-Reparse: The Trade-off Nobody Tells You About Instructor Streaming." Directly an interview story in prose.
- [ ] Final metrics review. Write "First Month of Spelix Beta" draft. Commit to `docs/metrics/2026-W19.md`.
- [ ] Publish "First Month" post. Anchor artifact for outreach in June-August.
- [ ] **Freeze Spelix feature work until August.** Open issues triaged: bug-only during Saturniq, no new features, no scope creep.
- [ ] **L2 retrospective.** What worked, what didn't, Phase 2 RAG eval plan using real user data. Commit to `docs/retros/2026-05-l2-retro.md`.

**Internship (~8 hrs):**

- [ ] Send 5 more alumni outreach DMs.
- [ ] Draft email/LinkedIn template for hiring managers (engineer-to-engineer, not recruiter-speak).
- [ ] Mock interview #1: friend, Pramp, or interviewing.io. AI/ML focused if possible.
- [ ] CV v2 updated with final L2 metrics.
- [ ] Monthly review: populate Fall 2026 app timeline with known open dates.

---

## Phase 2: Saturniq Period — L3 Autopilot (mid-May - mid-August 2026)

**Time budget:** 5-8 hrs/week, strict evenings/weekends only.

### Weekly Maintenance

- **Sunday 30-min metrics check** — signups, retention, production errors. Set up alerts so you don't babysit.
- **Every 2 weeks:** one blog post OR one community engagement (answer questions in relevant subreddit threads, not self-promo).
- **Bug fixes only.** No new features.
- **Collect Phase 2 RAG training data** — real user coaching queries, reviewed by kinesiology partner. Target: 300-500 reviewed coaching outputs by August for the golden dataset.

### Do NOT Do During Saturniq

- Ship Phase 2 to production
- Launch a marketing campaign
- Respond to hype if product goes mildly viral (triage with the runbook)
- Any L4 activity (payments, TOS, pricing, commercial launch)

### Internship Prep During Saturniq

- 3-5 LeetCodes/week minimum, weekend sessions
- 1 system design problem every 2 weeks
- Fundamentals study 2 hrs/week
- Mock interviews once a month
- **Have CV, cover letter templates, target list, and outreach threads ready by July 31.** Apply the day listings open.

### Saturniq Job Itself

The Saturniq internship is the biggest signal-generator in this whole period. Do extraordinary work there. Ask to own something real. The strongest Fall 2026 interview narrative is: "incoming Saturniq intern -> finished deliverable early -> took on a stretch project -> shipped something production traffic depends on." Don't shortchange it for Spelix.

---

## Phase 3: Post-Saturniq — Application Cycle (mid-August - October 2026)

**Spelix mode:** minimum viable maintenance. Interview prep dominates.

- Resume Phase 2 RAG work ONLY using collected golden dataset — ship minimal version with real eval numbers
- Application cycle: apply to 30-50 top AI + Canadian bigtech roles
- **Interview narrative (three pillars):** Saturniq internship + Spelix private beta with real users + Phase 2 RAG evals on real data
- LeetCode daily, mock interviews weekly, system design biweekly

---

## Interview Narrative Target

By September 2026, you should be able to say:

> "I shipped Spelix — a science-grounded AI barbell form coaching platform — to a private beta of 50+ lifters. The pipeline runs CV pose estimation through a 5-tier confidence model, GPT-4o keyframe analysis, and Claude coaching streamed over SSE. I instrumented retention, coaching quality ratings, and user sessions. 35 weekly active users, 71% said feedback was more specific than existing tools. Phase 2 adds citation-grounded RAG over peer-reviewed biomechanics literature — I collected 500 real coaching queries during the beta and built a golden eval dataset with a kinesiology partner. RAGAS faithfulness > 0.85 on that dataset."

That narrative + Saturniq internship story + strong interview performance = top-AI competitive.

---

## North Star Metrics (by phase)

| Phase | Metric | Target |
|-------|--------|--------|
| L2 (May 9) | Total beta users | 25-50 |
| L2 (May 9) | Weekly active users | 15-30 |
| L2 (May 9) | User sessions observed (in-person) | 3+ |
| L2 (May 9) | Coaching thumbs-up rate | >70% |
| L3 (August) | Total users | 100-200 |
| L3 (August) | Reviewed coaching outputs for RAG golden dataset | 300-500 |
| L3 (August) | Blog posts published | 4-6 |
| Fall 2026 | Applications sent to top-AI + bigtech | 30-50 |
| Fall 2026 | Interview conversion rate | >20% |
