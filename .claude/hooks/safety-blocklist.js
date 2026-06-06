#!/usr/bin/env node
// PreToolUse(Bash). Hard-blocks destructive commands. Exit 2 = block, 0 = allow.
// Contract: reads hook JSON on stdin; never blocks on malformed input.
let d = '';
process.stdin.on('data', (c) => (d += c));
process.stdin.on('end', () => {
  try {
    const j = JSON.parse(d);
    const c = j.tool_input?.command || '';
    const cl = c.toLowerCase();
    const BLOCK = [
      ['rm -rf /', 'wipe root'], ['rm -rf .', 'wipe cwd'], ['rm -rf ~', 'wipe home'],
      ['rm -rf *', 'wipe glob'], ['rm -rf c:', 'wipe drive'],
      ['rmdir /s /q', 'windows recursive nuke'], ['del /s /q /f', 'windows force nuke'],
      ['git push --force', 'force push'], ['git push -f ', 'force push'],
      ['git push origin main', 'direct push to main'], ['git push origin master', 'direct push to master'],
      ['git reset --hard', 'hard reset loses work'], ['git clean -fd', 'delete untracked files'],
      ['docker compose down -v', 'destroy volumes'], ['docker system prune -a', 'prune everything'],
      ['drop table', 'drop table'], ['drop database', 'drop database'], ['truncate ', 'truncate table'],
      ['alembic downgrade base', 'wipe all migrations'], ['npm publish', 'publish package'],
      ['supabase db reset', 'reset database'],
      ['chmod 777', 'world-writable'], ['chmod -r 777', 'recursive world-writable'],
      ['cat .env', 'read secrets via bash'], ['type .env', 'read secrets via bash'],
      ['curl|sh', 'pipe to shell'], ['curl |sh', 'pipe to shell'], ['curl | sh', 'pipe to shell'],
      ['wget|sh', 'pipe to shell'], ['wget |sh', 'pipe to shell'], ['wget | sh', 'pipe to shell'],
      ['curl|bash', 'pipe to shell'], ['curl | bash', 'pipe to shell'],
      ['wget|bash', 'pipe to shell'], ['wget | bash', 'pipe to shell'],
      ['> .env', 'overwrite env file'], ['>> .env', 'append to env file'],
    ];
    for (const [p, r] of BLOCK) {
      if (cl.includes(p)) {
        process.stderr.write(`\n\u{1F6AB} BLOCKED: ${r} — command: ${c}\n`);
        process.exit(2);
      }
    }
  } catch (e) { /* malformed input: allow */ }
  process.exit(0);
});
