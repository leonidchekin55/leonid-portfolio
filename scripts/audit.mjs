import assert from 'node:assert/strict';
const origin='https://leonid-portfolio.onrender.com';
for (const path of ['/', '/en.html','/pulseboard.html','/ai-engineer-tour.html','/privacy.html','/terms.html','/privacy-en.html','/terms-en.html']) {
 const r=await fetch(origin+path,{signal:AbortSignal.timeout(60000)});assert.equal(r.status,200,`${path} HTTP ${r.status}`);const body=await r.text();assert.match(body,/<html[^>]+lang=/i);assert.match(body,/name="viewport"/i);console.log('PASS',path);
 if(path==='/pulseboard.html')assert.match(body,/pulseboard-ui\.js\?v=4/);
 if(path==='/ai-engineer-tour.html')assert.match(body,/kind="captions"/);
}
for(const path of ['/assets/ai-engineer-portfolio-tour.mp4','/assets/ai-engineer-portfolio-tour.srt','/assets/ai-engineer-portfolio-tour-poster.png','/downloads/Leonid_Chekin_Resume_AI_RAG_ATS.pdf','/downloads/Leonid_Chekin_Resume_Backend_ATS.pdf','/downloads/Leonid_Chekin_Resume_English_ATS.pdf']){const r=await fetch(origin+path,{method:'HEAD',signal:AbortSignal.timeout(60000)});assert.equal(r.status,200,`${path} HTTP ${r.status}`);console.log('PASS asset',path)}
