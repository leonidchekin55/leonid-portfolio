import assert from 'node:assert/strict';
import { readdir, readFile } from 'node:fs/promises';
import path from 'node:path';

const pages = (await readdir('.')).filter((name) => name.endsWith('.html')).sort();
assert.ok(pages.length > 0, 'repository must contain HTML pages');

for (const page of pages) {
  const html = await readFile(page, 'utf8');
  assert.match(html, /<html\b[^>]*\blang=["'](?:ru|en)(?:-[A-Za-z0-9-]+)?["']/i, `${page} must declare its language`);
  assert.match(html, /<meta\b[^>]*name=["']viewport["']/i, `${page} must set a mobile viewport`);
  assert.match(html, /<title\b[^>]*>\s*[^<]+/i, `${page} must have a non-empty title`);
  for (const match of html.matchAll(/<img\b([^>]*)>/gi)) {
    assert.match(match[1], /\balt\s*=/i, `${page} has an image without alt text`);
  }
  for (const match of html.matchAll(/\b(?:href|src)=["']([^"']+)["']/gi)) {
    const target = match[1].trim();
    if (!target || /^(?:[a-z][a-z\d+.-]*:|\/\/|#)/i.test(target)) continue;
    const localPath = decodeURIComponent(target.split(/[?#]/, 1)[0]);
    if (!localPath) continue;
    const resolved = path.normalize(localPath.startsWith('/') ? `.${localPath}` : path.join('.', localPath));
    assert.ok(!resolved.startsWith('..'), `${page} contains a path outside the site: ${target}`);
    const filePath = resolved.endsWith(path.sep) ? path.join(resolved, 'index.html') : resolved;
    try {
      await readFile(filePath);
    } catch {
      assert.fail(`${page} points to missing local file: ${target}`);
    }
  }
  console.log('PASS HTML source', page);
}

const sitemap = await readFile('sitemap.xml', 'utf8');
for (const [, url] of sitemap.matchAll(/<loc>\s*([^<]+)\s*<\/loc>/gi)) {
  const pathname = new URL(url).pathname;
  const sitePath = pathname.endsWith('/') ? `${pathname}index.html` : pathname;
  try {
    await readFile(path.normalize(`.${sitePath}`));
  } catch {
    assert.fail(`sitemap.xml points to missing local page: ${url}`);
  }
}
console.log('PASS sitemap local pages');

const pulseboard = await readFile('pulseboard.html', 'utf8');
assert.match(pulseboard, /pulseboard-ui\.js\?v=5/, 'Pulseboard page must load the current script version');
const script = await readFile('pulseboard-ui.js', 'utf8');
assert.equal([...script.matchAll(/\bconst\s+memory\b/g)].length, 1, 'Pulseboard storage variable must be declared once');
assert.match(script, /window\.sessionStorage/, 'Demo access token must remain tab scoped');
console.log('PASS Pulseboard script and session storage');
