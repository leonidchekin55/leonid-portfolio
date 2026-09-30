import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

for (const path of ['index.html', 'en.html', 'pulseboard.html', 'ai-engineer-tour.html', 'privacy.html', 'terms.html', 'privacy-en.html', 'terms-en.html']) {
  const html = await readFile(path, 'utf8');
  assert.match(html, /<html[^>]+lang="(ru|en)"/i, `${path} must declare its language`);
  assert.match(html, /name="viewport"/i, `${path} must set a mobile viewport`);
  assert.doesNotMatch(html, /<img(?![^>]*\balt=)[^>]*>/i, `${path} has an image without alt text`);
  console.log('PASS source', path);
}

const pulseboard = await readFile('pulseboard.html', 'utf8');
assert.match(pulseboard, /pulseboard-ui\.js\?v=5/, 'Pulseboard page must load the current script version');
const script = await readFile('pulseboard-ui.js', 'utf8');
assert.equal([...script.matchAll(/\bconst\s+memory\b/g)].length, 1, 'Pulseboard storage variable must be declared once');
assert.match(script, /window\.sessionStorage/, 'Demo access token must remain tab scoped');
console.log('PASS source Pulseboard script and session storage');
