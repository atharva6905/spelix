# e2e/ — End-to-End Test Artifacts

Files used by the manual Playwright MCP E2E verification workflow described in root `CLAUDE.md` ("E2E Verification via Playwright MCP") and `.claude/commands/handoff.md`.

## Structure

```
e2e/
  README.md             # this file
  fixtures/             # video inputs for live upload flow testing
    squat-high-bar.mp4  # ~10s, 720p, side view, ~733 KB — squat high-bar fixture
  screenshots/          # artifacts captured during E2E runs against spelix.app
    e2e-01-upload-initial.png
    e2e-02-upload-cors-error.png
```

## Using the fixture

The fixture is attached to the live upload form at `https://spelix.app/upload` via the Playwright MCP `browser_file_upload` tool. Example (from session 11):

```
mcp__playwright__browser_file_upload(paths=["C:\\Users\\athar\\projects\\spelix\\e2e\\fixtures\\squat-high-bar.mp4"])
```

Use an absolute path — the MCP tool does not resolve paths relative to the working directory.

## Adding new fixtures

Keep fixtures small (≤ 5 MB, ≤ 15 s, 720p). The fixture set exists to exercise the full production pipeline (upload → pose extraction → rep detection → scoring → coaching → PDF) in under a minute per run. Larger videos slow down the session and risk hitting the 50 MB upload cap (`MAX_FILE_SIZE_BYTES` in `backend/app/schemas/analysis.py`).

One fixture per exercise variant is enough. Current set:
- `squat-high-bar.mp4` — high-bar back squat, sagittal view

Planned additions (as Phase 2 E2E coverage grows):
- `bench-flat.mp4`
- `deadlift-conventional.mp4`
- `squat-low-bar.mp4` (lower-priority variant coverage)

## Screenshots

`screenshots/` captures visible-viewport PNGs from the most recent E2E run. Re-runs overwrite or append with date-stamped prefixes — session 11 used `e2e-01-*`, `e2e-02-*`, etc. If a session captures many shots across multiple flows, consider adding a subdirectory per run date: `screenshots/2026-04-11/`.

## What's NOT in here

- **`.playwright-mcp/`** (gitignored) — the Playwright MCP tool auto-writes accessibility-tree YAML snapshots, console logs, and network request dumps there. Those files are large and noisy; keep them out of the repo. Reference them by path in handoff notes only.
- **Vitest / pytest** — unit tests live in `frontend/src/**/__tests__/` and `backend/tests/` respectively. Those are not E2E.
- **CI deploy smoke tests** — TODO item from session 11 handoff, not yet implemented. If/when added, they belong in `.github/workflows/ci.yml` as a post-deploy job, not here.
