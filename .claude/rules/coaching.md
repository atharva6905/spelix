---
description: Coaching, LLM, and SaMD language rules
paths:
  - "backend/app/services/coach*"
  - "backend/app/services/chat*"
  - "backend/app/api/v1/coaching*"
  - "backend/app/prompts/**"
  - "reports/templates/**"
---
# Coaching & Language Rules

- NEVER use "injury risk" or "injury prevention" in any user-facing string — use "Movement Quality".
  Internal field `form_score_safety`; user-facing label "Movement Quality". Applies to prompts,
  frontend copy, PDF templates, error messages. Single violation = CRITICAL (security reviewer).
- Coaching model: Claude Sonnet 4.6 with prompt caching; keyframes/auto-detect fallback: GPT-4o.
- CoVe claim extraction is principle-level with inversion + extrapolation guards (ADR-COVE-02/03).
- Never persist raw `str(exc)` to admin-visible DB columns (ADR-DISTILL-05).
- Always use the `spelix-coaching-engineer` agent for coaching service / SSE / prompt work.
