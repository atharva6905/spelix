export const meta = {
  name: 'srs-audit',
  description: 'Fan out spelix-auditor over SRS sections; merged, deduped verdict table',
  whenToUse: 'After every batch merge and at phase gates',
  phases: [{ title: 'Audit' }, { title: 'Merge' }],
}
const FINDINGS = {
  type: 'object', required: ['findings'],
  properties: { findings: { type: 'array', items: { type: 'object',
    required: ['requirement', 'severity', 'file', 'detail'],
    properties: { requirement: { type: 'string' }, severity: { enum: ['CRITICAL', 'HIGH', 'MEDIUM'] },
      file: { type: 'string' }, detail: { type: 'string' } } } } },
}
// Current-phase MUST sections of docs/SRS.md, audited independently.
const SECTIONS = ['CV pipeline (FR-CVPL, FR-SCOR)', 'Coaching (FR-AICP, FR-COACH)',
  'RAG & Coach Brain (FR-RAGK, FR-BRAIN)', 'Upload/auth/profiles (FR-VUPL, FR-AUTH, FR-PROF)',
  'Reports & UI (FR-REPM, FR-UIUX)']
const all = await parallel(SECTIONS.map((s) => () =>
  agent(`Audit implemented code against docs/SRS.md section scope: ${s}. FIRST read your MEMORY.md and consult prior findings for this section. Trace full call paths before marking anything CRITICAL/MISSING (false-positive protocol). Update your MEMORY.md with new/resolved findings BEFORE returning the structured verdict, then report findings.`,
    { label: `audit:${s.split(' ')[0]}`, phase: 'Audit', agentType: 'spelix-auditor', schema: FINDINGS })))
const findings = all.filter(Boolean).flatMap((r) => r.findings)
const seen = new Set(); const deduped = []
for (const f of findings) { const k = `${f.requirement}|${f.file}`; if (!seen.has(k)) { seen.add(k); deduped.push(f) } }
log(`${deduped.length} unique finding(s) across ${SECTIONS.length} sections`)
return { findings: deduped }
