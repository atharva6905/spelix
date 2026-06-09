export const meta = {
  name: 'coverage-sweep',
  description: 'Find coverage gaps, write tests per module in worktree isolation, verify green',
  whenToUse: 'Periodic test-debt paydown without burning a main session',
  phases: [{ title: 'Discover' }, { title: 'Write' }, { title: 'Verify' }],
}
const GAPS = { type: 'object', required: ['modules'], properties: { modules: { type: 'array',
  items: { type: 'object', required: ['path', 'uncovered'], properties: {
    path: { type: 'string' }, uncovered: { type: 'string' } } }, maxItems: 6 } } }
const RESULT = { type: 'object', required: ['module', 'testsAdded', 'suiteGreen'], properties: {
  module: { type: 'string' }, testsAdded: { type: 'number' }, suiteGreen: { type: 'boolean' },
  branch: { type: 'string' } } }
const gaps = await agent(
  'cd backend && uv run pytest --cov=app --cov-report=term-missing -q --ignore=tests/unit/test_pose_extraction.py. Rank the 6 modules with the largest coverage gaps (skip config/type-stub files). Return path + uncovered-lines summary per module.',
  { label: 'discover-gaps', phase: 'Discover', schema: GAPS })
const results = await pipeline(
  (gaps?.modules || []),
  (m) => agent(`In backend/, write focused pytest unit tests covering the uncovered lines of ${m.path} (${m.uncovered}). Follow existing test conventions in backend/tests/unit/. Run the new tests until green. Commit with message "test: cover ${m.path}". Return module, testsAdded, suiteGreen, branch.`,
    { label: `tests:${m.path.split('/').pop()}`, phase: 'Write', isolation: 'worktree', agentType: 'spelix-tdd', schema: RESULT }),
)
const ok = results.filter(Boolean).filter((r) => r.suiteGreen)
log(`${ok.length}/${results.filter(Boolean).length} modules green — merge worktree branches into ONE PR manually`)
return { results: ok }
