// Test-only gh simulator. Default-exports async (argsArray) -> stdout string.
// DB at process.env.CLAIMS_SHIM_DB: { issues:{"<n>":{number,title,labels:[...]}}, labels:[...], comments:[] }
import { readFileSync, writeFileSync } from 'node:fs';
const DB = () => process.env.CLAIMS_SHIM_DB;
const read = () => JSON.parse(readFileSync(DB(), 'utf8'));
const write = (d) => writeFileSync(DB(), JSON.stringify(d, null, 2));

export default async function gh(args) {
  const d = read();
  const [a0, a1] = args;
  if (a0 === 'issue' && a1 === 'list') {
    return JSON.stringify(Object.values(d.issues).map((i) => ({
      number: i.number, title: i.title, labels: i.labels.map((n) => ({ name: n })),
    })));
  }
  if (a0 === 'issue' && a1 === 'view') {
    const i = d.issues[args[2]];
    return JSON.stringify({ labels: (i ? i.labels : []).map((n) => ({ name: n })) });
  }
  if (a0 === 'issue' && a1 === 'edit') {
    const i = d.issues[args[2]];
    const add = args.indexOf('--add-label'); const rem = args.indexOf('--remove-label');
    if (add > -1 && i && !i.labels.includes(args[add + 1])) i.labels.push(args[add + 1]);
    if (rem > -1 && i) i.labels = i.labels.filter((n) => n !== args[rem + 1]);
    write(d); return '';
  }
  if (a0 === 'issue' && a1 === 'comment') { (d.comments ??= []).push({ n: args[2], body: args[args.indexOf('--body') + 1] }); write(d); return ''; }
  if (a0 === 'label' && a1 === 'create') { if (!d.labels.includes(args[2])) d.labels.push(args[2]); write(d); return ''; }
  if (a0 === 'label' && a1 === 'list') { return JSON.stringify(d.labels.map((n) => ({ name: n }))); }
  if (a0 === 'label' && a1 === 'delete') { d.labels = d.labels.filter((n) => n !== args[2]); write(d); return ''; }
  throw new Error(`ghshim: unhandled args ${JSON.stringify(args)}`);
}
