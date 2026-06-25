// Pre-transpile the dashboard JSX -> plain JS so the browser loads compiled
// React.createElement code directly (no in-browser @babel/standalone). This
// removes the ~10s transpile-on-load (the blank-page window) and the unpkg
// babel download.
//
// Usage:  node tools/build_dashboard.mjs
// Requires @babel/standalone (npm i --no-save @babel/standalone). The wrapper
// tools/build_dashboard.py installs it on demand and runs this.
//
// Re-run after editing any gui/dashboard/*.jsx file. The generated *.js are
// committed so the dashboard works without a build step at serve time.
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import * as babel from '@babel/standalone';

const here = dirname(fileURLToPath(import.meta.url));
const dashDir = join(here, '..', 'gui', 'dashboard');

// Order matters at load time; transpile each independently (classic runtime,
// React/ReactDOM are globals from the UMD scripts).
const FILES = ['shared.jsx', 'direction_b.jsx', 'direction_b_pages.jsx', 'app.jsx'];

let ok = 0;
for (const f of FILES) {
  const src = readFileSync(join(dashDir, f), 'utf8');
  const out = babel.transform(src, {
    presets: ['react'],
    filename: f,
    compact: false,
    retainLines: false,
  }).code;
  const dest = f.replace(/\.jsx$/, '.js');
  const banner = `// GENERATED from ${f} by tools/build_dashboard.mjs — do not edit; edit the .jsx and rebuild.\n`;
  writeFileSync(join(dashDir, dest), banner + out, 'utf8');
  console.log(`  ${f} -> ${dest} (${out.length} bytes)`);
  ok++;
}
console.log(`build_dashboard: transpiled ${ok}/${FILES.length} files`);
