---
description: Frontend hard rules
paths:
  - "frontend/**"
---
# Frontend Rules

- React 19, Vite 8 (NOT Next.js — no SSR assumptions, ADR-026), TypeScript strict, Tailwind CSS 4, shadcn/ui.
- Language rules enforced in copy: "Movement Quality", never "injury risk" (see coaching rules).
- TUS upload bypasses FastAPI — talks to Supabase Storage directly.
- Regenerate Supabase types after backend API changes (`frontend/CLAUDE.md` → Types section).
- Tests: vitest; mock Supabase client per frontend/CLAUDE.md patterns.
