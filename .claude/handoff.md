# Session 18 Handoff → Session 19: Batch 6 complete — citation tooltips + follow-up chat

## Completed

| Task | PR | Squash SHA | Description |
|------|----|------------|-------------|
| P2-021 | #22 | `5cce808` | Citation tooltips (FR-RESL-06). `parseWithCitations()` in `CitationTooltip.tsx` splits `[N]` markers into superscript `<button>` elements with CSS-only hover/focus tooltips (title, authors, year, DOI link). Wired into summary, strengths, issues, correction_plan in `ResultsPage.tsx`. Degraded-mode amber banner when `degraded_mode=true` (FR-AICP-15). Types updated: `CoachingIssue.citation_indices`, `CoachingOutput.degraded_mode`. |
| P2-022 | #23 | `0173006` | Follow-up chat (FR-RESL-09, FR-AICP-17). **Backend**: migration 005 `chat_messages` table, `ChatMessage` model, `ChatMessageRepository`, `ChatService` (Claude Sonnet 4.6, non-streaming, context = coaching_result + retrieved_sources), `SafetyFilter.apply_text()`, POST+GET `/analyses/{id}/chat` with 30/day rate limit. **Frontend**: `useChat` hook (history load, optimistic send, error rollback), `ChatPanel` component (message list, typing indicator, Enter-to-send), mounted below coaching on ResultsPage. |
| — | — | `5632077` | Handoff + backlog docs commit (superseded by this file). |
| ADRs | — | pending | ADR-P2-021 (CSS-only tooltips), ADR-P2-022a (non-streaming chat MVP), ADR-P2-022b (SafetyFilter.apply_text). |
| Backlog fix | — | pending | P2-013/014/015/016 rows corrected from `open` to `done` with correct PR SHAs (stale from session 16-17). |

### Infra actions completed
- Droplet containers rebuilt (`docker compose build --no-cache backend worker`)
- Migration 005 applied via direct SQL from container (`CREATE TABLE chat_messages ...`)
- Alembic version updated: `004_phase2_rag_coach_brain` → `005_add_chat_messages`
- Containers healthy: backend (Up, healthy), worker (Up), redis (Up, healthy)

## Remaining

### Phase 2 Batch 7 — Coach Brain Foundation
| ID | Status | Deps met? | Notes |
|----|--------|-----------|-------|
| P2-025 | open | ✅ (P2-023 + P2-024 done) | Seed corpus ingestion (≥20 entries) |
| P2-026 | open | ✅ (P2-023 + P2-010 done) | Coach Brain hybrid retrieval + routing logic |
| P2-027 | open | blocked on P2-026 | Cold-start fallback |
| P2-029 | open | ✅ (P2-001 done) | Three-tier consent UI |
| P2-030 | open | blocked on P2-029 | Consent withdrawal cascade |
| P2-031 | open | no deps | DPIA — hard privacy gate |

### Phase 2 Batch 8 — Eval Logging (all deps met)
| ID | Status | Deps met? | Notes |
|----|--------|-----------|-------|
| P2-032 | open | ✅ | Per-analysis RAGAS/HHEM eval scores |
| P2-033 | open | ✅ | Retrieval metrics logging |
| P2-034 | open | ✅ | Langfuse Cloud setup |

### Tech debt (no deps)
| ID | Status | Notes |
|----|--------|-------|
| D-004..D-010 | open | Session 13 cleanup items. D-005 (720p fixture) blocks D-008. |
| P2-007 | open | Corpus curation — seed research papers (data work, not code) |

## Test counts

- **Backend**: 1242 passed / 19 skipped / 0 failures (+13 new from P2-022)
- **Frontend**: 212 passed / 0 failures (+17 new from P2-021 + P2-022)
- **Coverage**: ~91% backend (CI enforces ≥90%)
- **Known local-only failures**: 2 DB-dependent integration tests (`test_models.py::test_cascade_delete_rep_metrics`, `test_repositories.py::test_delete_removes_row`) fail locally because they connect to Supabase prod which had the old schema. CI passes — it uses `scripts/create_test_tables.py` which reflects all models including `ChatMessage`.
- **Alembic head**: `005_add_chat_messages` (applied on droplet)

## E2E verification

**Not yet performed** — PR #22 and #23 merged to main today. Vercel frontend deploys automatically; droplet containers rebuilt and restarted with new code + migration 005 applied.

**Verify in next session** (after deploy settles ~2 min):
1. `mcp__playwright__browser_navigate` → `https://spelix.app`
2. Login, navigate to a completed analysis results page
3. **Citation markers**: verify `[N]` superscript buttons appear in coaching text sections
4. **Tooltip**: hover a citation marker → tooltip shows title/authors/year + DOI link
5. **Chat panel**: scroll below coaching → "Ask a follow-up question" panel visible
6. **Send message**: type a question, press Enter → verify assistant response appears
7. **Safety language**: no "injury risk" or "injury prevention" in any coaching or chat text
8. **Degraded mode**: (only testable if Qdrant is offline — skip unless simulating)
9. `browser_console_messages` level=error → should be empty
10. `browser_network_requests` → no 4xx/5xx

## Blockers

None. All Batch 6 deps were met. Qdrant/Cohere/Anthropic env vars confirmed on droplet from session 17.

## Next session start

```bash
/status
```

Then either:
- **Batch 7 (P2-025, P2-026)** — Coach Brain seed corpus ingestion + hybrid retrieval routing. Requires `spelix-rag-engineer` agent. P2-025 is data work (curating ≥20 coach brain entries); P2-026 is code.
- **Batch 8 (P2-032–034)** — Eval logging. All deps met. Pure backend work. Good choice if Coach Brain corpus data isn't ready yet.
- **E2E verification first** — run Playwright MCP against spelix.app to verify Batch 5+6 features before starting new work.
