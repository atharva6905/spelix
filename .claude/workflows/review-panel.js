export const meta = {
  name: 'review-panel',
  description: 'Multi-dimension adversarial review of a diff (T3 / deep pre-merge gate)',
  whenToUse: 'Before merging T3 changes: migrations on data, RLS, coaching prompts, consent flows',
  phases: [{ title: 'Review' }, { title: 'Verify' }],
}
// args: { ref: string } — branch name or PR head to review against main
const ref = (args && args.ref) || 'HEAD'
const FINDINGS = {
  type: 'object', required: ['findings'],
  properties: { findings: { type: 'array', items: { type: 'object',
    required: ['title', 'file', 'severity', 'detail'],
    properties: { title: { type: 'string' }, file: { type: 'string' },
      severity: { enum: ['CRITICAL', 'HIGH', 'MEDIUM'] }, detail: { type: 'string' } } } } },
}
const VERDICT = { type: 'object', required: ['isReal', 'reason'],
  properties: { isReal: { type: 'boolean' }, reason: { type: 'string' } } }
const DIMS = [
  { key: 'correctness', prompt: `Review the diff of ${ref} vs origin/main (git diff origin/main...${ref}) for correctness bugs: logic errors, broken contracts, missing error paths, async/await misuse. Spelix: FastAPI + SQLAlchemy 2.0 + streaq worker.` },
  { key: 'security-samd', prompt: `Review the diff of ${ref} vs origin/main for: SaMD language violations (any user-facing "injury" string = CRITICAL; correct term "Movement Quality"), JWT/RLS gaps, secret exposure, injection. Read .claude/rules/coaching.md and .claude/claude-security-guidance.md first.` },
  { key: 'perf-droplet', prompt: `Review the diff of ${ref} vs origin/main for performance on a 4GB DigitalOcean droplet: memory spikes (video frames in RAM), blocking calls on the event loop, N+1 queries, unbounded result sets. Read .claude/rules/cv-pipeline.md memory budget first.` },
  { key: 'srs-compliance', prompt: `Review the diff of ${ref} vs origin/main against docs/SRS.md: does it violate any Must requirement, misuse SRS terminology, or contradict an Accepted ADR in decisions.md?` },
]
const results = await pipeline(
  DIMS,
  (d) => agent(d.prompt + ' Return findings only — no praise.', { label: `review:${d.key}`, phase: 'Review', schema: FINDINGS }),
  (review) => parallel((review?.findings || []).map((f) => () =>
    agent(`Adversarially verify this code-review finding. Try to REFUTE it by reading the actual code. Finding: ${f.title} in ${f.file}: ${f.detail}. Default isReal=false if you cannot reproduce the concern from the code.`,
      { label: `verify:${f.title.slice(0, 30)}`, phase: 'Verify', schema: VERDICT })
      .then((v) => ({ ...f, verdict: v })))),
)
const confirmed = results.flat().filter(Boolean).filter((f) => f.verdict?.isReal)
log(`${confirmed.length} confirmed finding(s)`)
return { confirmed }
