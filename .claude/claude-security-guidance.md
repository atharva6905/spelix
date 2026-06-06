# Spelix Security Guidance (security-guidance plugin config)

Project-specific severities — treat each as HIGH unless stated:
- SaMD language: any user-facing "injury risk"/"injury prevention" string = CRITICAL.
  Correct term: "Movement Quality". Applies to backend prompts, frontend copy, PDF
  templates, error messages.
- JWT: ES256 signature verification, `exp` and `iss` claims mandatory on every protected
  route. Never widen the accepted-algorithms list (HS256 alongside ES256 = algorithm
  confusion). Never drop issuer validation.
- RLS: views bypass RLS; UPDATE policies need matching SELECT; never use user_metadata in
  policies (user-editable). No DDL FK to auth.users.
- Storage: artifacts are private; access via signed read URLs only (ADR-042).
- Secrets: SUPABASE_SERVICE_ROLE, ANTHROPIC_API_KEY, sk- prefixed keys must never appear
  in code, logs, error messages, or admin-visible DB columns (ADR-DISTILL-05 — never
  persist raw `str(exc)`).
- Upload validation: ≤500MB, extension + MIME checks (FR-VUPL).
- GDPR Art. 9: health-data processing requires explicit consent; consent-withdrawal
  cascades (FR-BRAIN-16); consent gate before upload (ADR-CONSENT-GATE-01).
- Merge governance: `.claude/rules/governance.md` tiers are binding — flag any agent
  attempting autonomous changes to settings.json, .claude/hooks/**, or governance.md.
