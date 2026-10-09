import assert from 'node:assert/strict';
const origin='https://leonid-portfolio.onrender.com';
for (const path of ['/', '/en.html','/pulseboard.html','/ai-engineer-tour.html','/privacy.html','/terms.html','/privacy-en.html','/terms-en.html']) {
 const url=path==='/pulseboard.html'?`${origin}${path}?audit=${Date.now()}`:origin+path;
 const r=await fetch(url,{signal:AbortSignal.timeout(60000)});assert.equal(r.status,200,`${path} HTTP ${r.status}`);const body=await r.text();assert.match(body,/<html[^>]+lang=/i);assert.match(body,/name="viewport"/i);console.log('PASS',path);
 if(path==='/pulseboard.html')assert.match(body,/pulseboard-ui\.js\?v=\d+/);
 if(path==='/ai-engineer-tour.html')assert.match(body,/kind="captions"/);
 if(path==='/atlas-studio-demo.html')assert.equal([...body.matchAll(/class="card"/g)].length,15,'ATLAS showcase must include 15 demo modules');
}
let atlasPublished = false;
for (let attempt = 0; attempt < 24; attempt += 1) {
 const page = await fetch(`${origin}/atlas-studio-demo.html?audit=${Date.now()}`, {signal:AbortSignal.timeout(60000)});
 if (page.status === 200) {
  const body = await page.text();
  if ((body.match(/^\s*\['/gm) || []).length === 15) {
   assert.match(body, /name="viewport"/i);
   console.log('PASS published ATLAS showcase · 15 modules');
   atlasPublished = true;
   break;
  }
 }
 console.log(`Waiting for Render ATLAS deploy (${attempt + 1}/24)`);
 await new Promise(resolve => setTimeout(resolve, 10000));
}
assert.ok(atlasPublished, 'Render did not publish the ATLAS showcase within four minutes');
let deployedPulseboard = false;
for (let attempt = 0; attempt < 24; attempt += 1) {
 const page = await fetch(`${origin}/pulseboard.html?audit=${Date.now()}`, {signal:AbortSignal.timeout(60000)});
 assert.equal(page.status, 200, `Pulseboard page HTTP ${page.status}`);
 if (/pulseboard-ui\.js\?v=5/.test(await page.text())) {
  const asset = await fetch(`${origin}/pulseboard-ui.js?v=5&audit=${Date.now()}`, {signal:AbortSignal.timeout(60000)});
  assert.equal(asset.status, 200, `Pulseboard JavaScript HTTP ${asset.status}`);
  const source = await asset.text();
  assert.equal([...source.matchAll(/\bconst\s+memory\b/g)].length, 1, 'Published Pulseboard storage declaration');
  assert.doesNotThrow(() => new Function(source), 'Published Pulseboard JavaScript must parse');
  console.log('PASS published Pulseboard JavaScript');
  deployedPulseboard = true;
  break;
 }
 console.log(`Waiting for Render static deploy (${attempt + 1}/24)`);
 await new Promise(resolve => setTimeout(resolve, 10000));
}
assert.ok(deployedPulseboard, 'Render did not publish Pulseboard script version 5 within four minutes');
for(const path of ['/assets/ai-engineer-portfolio-tour.mp4','/assets/ai-engineer-portfolio-tour.srt','/assets/ai-engineer-portfolio-tour-poster.png','/downloads/Leonid_Chekin_Resume_AI_RAG_ATS.pdf','/downloads/Leonid_Chekin_Resume_Backend_ATS.pdf','/downloads/Leonid_Chekin_Resume_English_ATS.pdf']){const r=await fetch(origin+path,{method:'HEAD',signal:AbortSignal.timeout(60000)});assert.equal(r.status,200,`${path} HTTP ${r.status}`);console.log('PASS asset',path)}
