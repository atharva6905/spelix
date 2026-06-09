---
name: design
description: Turn an idea, feature request, or under-specified issue into a validated spec, implementation plan, and groomed GitHub issues. Use for any work with open design questions, multiple viable approaches, new user-facing surface, or 3+ files — before any code. Not for executing existing well-groomed issues (use /ship-loop) or single-file obvious changes.
argument-hint: "<idea | issue#> [--brainstorm | --plan-only]"
---
# Design

The ideation/planning harness. Runs in the MAIN session (interactive — the human is
the design partner). Terminal state: groomed GitHub issues that /ship-loop can execute.
This skill never writes implementation code.

## Step 1 — Route (before any exploration)

Assess the input:
- OPEN-ENDED (open design questions, multiple viable approaches, new user-facing
  surface, conceptually touches T2 paths) → Step 2 (brainstorm chain).
- WELL-SPECIFIED (requirements clear, approach obvious, multi-step) → Step 3
  (plan directly).
- TRIVIAL (single file, obvious change) → STOP: recommend filing an issue
  directly and running /ship-loop. Do not ceremonialize.

`--brainstorm` forces Step 2; `--plan-only` forces Step 3.
Input may be an existing issue number (e.g. labeled `needs-design` by groom):
read it with `mcp__github__get_issue` first.

## Step 2 — Brainstorm (nested)

**REQUIRED SUB-SKILL:** invoke `superpowers:brainstorming` via the Skill tool.

Spelix overrides (these take precedence over the skill's defaults):
1. Specs → `docs/internal/specs/YYYY-MM-DD-<topic>-spec.md`. NEVER commit
   (gitignored; local-planning-docs policy). Skip the skill's commit steps.
2. Use AskUserQuestion for option picks (previews when comparing approaches);
   one question per call.
3. Spec must cite FR-IDs, use SRS terminology exactly, and apply the SaMD
   language check to any proposed user-facing copy ("Movement Quality",
   never "injury").
4. The terminal handoff invokes superpowers:writing-plans with the Step 3
   overrides below — never frontend-design or any implementation skill.

## Step 3 — Plan (nested)

**REQUIRED SUB-SKILL:** invoke `superpowers:writing-plans` via the Skill tool.

Spelix overrides:
1. Plans → `docs/internal/plans/YYYY-MM-DD-<topic>-plan.md`. NEVER commit.
2. Every plan task carries a Spelix header: FR-ID(s), provisional governance tier
   (per `.claude/rules/governance.md`), target implementer (per the /implement
   routing table), and the TDD gate command.
3. The plan's execution-handoff section points at /ship-loop via the issues filed
   in Step 4 — superpowers:subagent-driven-development and superpowers:executing-plans
   are NOT used in this harness.

## Step 4 — File issues and hand off

For each coherent shippable unit in the plan, `mcp__github__create_issue`:
- Body: goal, FR-IDs, full task checklist EMBEDDED VERBATIM (execution must not
  depend on the local plan file), TDD gates, local plan doc path.
- Labels: `size/XS–XL`, provisional tier, `designed`.

Then offer: "queue is ready — hand to /ship-loop now?" If yes, invoke /ship-loop
with the new issue numbers in this session.

## Cross-domain contract note

If a plan contains tasks where two implementers must agree on a shared interface
(e.g. backend API shape + frontend consumer), do NOT parallelize them — make the
contract itself an explicit early task (schema/type definition + tests), then let
dependent tasks execute sequentially against it.
