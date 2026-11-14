// Build only the public frontend; backend code and credentials never enter dist/.
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const source = resolve(root, 'web');
const output = resolve(process.argv[2] || resolve(root, 'dist'));
if (output === root || output === source) throw new Error('Output must be separate from source.');
const files = ['index.html', 'workshop.css', 'workshop.js', 'progress.json'];
const contents = files.map(name => {
  const bytes = readFileSync(resolve(source, name));
  if (!bytes.length) throw new Error(`Empty frontend asset: ${name}`);
  return [name, bytes];
});
JSON.parse(contents.find(([name]) => name === 'progress.json')[1].toString());
mkdirSync(output, { recursive: true });
for (const [name, bytes] of contents) writeFileSync(resolve(output, name), bytes);
console.log(`Frontend ready: ${files.length} public files in ${output}`);
