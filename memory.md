# memory.md — Agent Persistent State

phase: 0
task: B-001
status: not_started
last_modified: []
failing_tests: []
blockers: [supabase_project_not_created, droplet_not_provisioned]
srs_deviations: []
next_action: "Run setup checklist steps 1-4, then begin B-001"
session_count: 0
last_session: null

## decisions_since_plan
<!-- Log any decision made during implementation that wasn't in decisions.md -->

## notes
- Repo is greenfield — only CLAUDE.md files, SRS, diagrams, .gitignore exist
- GSD hooks active on local PC — may prompt workflow guards on writes
- Supabase project must be created before B-002
- DO droplet deferred — dev runs locally against Supabase cloud
