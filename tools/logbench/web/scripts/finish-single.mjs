// vite always emits index.html; give the committed bundle a name that says what it is.
// server/export.py loads exactly this path.
import { renameSync, existsSync, statSync } from 'node:fs';

const from = new URL('../../server/assets/index.html', import.meta.url);
const to = new URL('../../server/assets/player.singlefile.html', import.meta.url);

if (!existsSync(from)) {
  console.error('expected a build at', from.pathname);
  process.exit(1);
}
renameSync(from, to);
console.log(`player.singlefile.html  ${(statSync(to).size / 1024).toFixed(1)} kB`);
