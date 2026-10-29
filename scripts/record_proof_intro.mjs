// The new first 30 seconds: a phone photo of a payment screen is dropped in -> the numbers it read light up on the
// photo -> photo vs ledger; then the same screen with the amount edited -> "a payment the ledger has never seen".
// Headless (no window). Writes a .webm plus marks.json (second at which each beat starts) for the video builder.
//   .venv/bin/uvicorn app.main:app --port 8765 &            # LOCAL mode (OCR boxes need macOS), real key in .env.local
//   node scripts/record_proof_intro.mjs http://127.0.0.1:8765 docs/video/intro1 [trueImage] [doctoredImage]
// Defaults: the first true and first doctored example in app/proof_examples/examples.json.
import { chromium } from '/Users/ollekil/Desktop/Moahub-Labs/webs/알리기팔기작전/홍보엔진/node_modules/playwright/index.mjs';
import fs from 'node:fs';
import path from 'node:path';

const [base = 'http://127.0.0.1:8765', out = 'docs/video/intro1', imgTrue, imgDoc] = process.argv.slice(2);
const ex = JSON.parse(fs.readFileSync('app/proof_examples/examples.json', 'utf8'));
const pick = k => ex.find(e => e.kind === k);
const T = imgTrue ? { file: imgTrue, message: pick('true').message } : { file: `app/proof_examples/${pick('true').id}.jpg`, message: pick('true').message };
const D = imgDoc ? { file: imgDoc, message: pick('doctored').message } : { file: `app/proof_examples/${pick('doctored').id}.jpg`, message: pick('doctored').message };
fs.mkdirSync(out, { recursive: true });
const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, recordVideo: { dir: out, size: { width: 1440, height: 900 } } });
const p = await ctx.newPage();
const t0 = Date.now(); const marks = {};
const mark = k => { marks[k] = +((Date.now() - t0) / 1000).toFixed(2); console.log(k, marks[k]); };
const waitResult = async () => p.waitForFunction(() => !document.querySelector('#go').disabled && document.querySelector('#out')?.children.length > 0 && !/Reading|읽는 중|Investigating|조사 중/.test(document.querySelector('#status')?.textContent || ''), null, { timeout: 300000 });
const failed = async () => p.evaluate(() => { const m = document.body.innerText.match(/.{0,60}(failed|실패|FAKE).{0,40}/); return m ? m[0] : ''; });

await p.request.post(base + '/api/reset');
await p.goto(base); await p.addStyleTag({ content: 'body{zoom:1.25}' }); await p.waitForTimeout(1200); mark('home');

for (const [k, shot] of [['true', T], ['doctored', D]]) {
  await p.fill('#msg', ''); await p.type('#msg', shot.message, { delay: 14 }); mark(`${k}_typed`);
  await p.setInputFiles('#photo', path.resolve(shot.file)); await p.waitForTimeout(900); mark(`${k}_dropped`);
  await p.click('#go'); mark(`${k}_click`);
  await waitResult(); mark(`${k}_result`);
  { const fw = await failed(); if (fw) console.log(`WARNING (${k}):`, fw); }
  const card = await p.$('h2:has-text("What the photo says"), h2:has-text("사진이 말하는")');
  if (card) { await p.evaluate(e => e.scrollIntoView({ behavior: 'smooth', block: 'start' }), card); }
  await p.waitForTimeout(1600); mark(`${k}_highlight`);   // boxes fade in (0.6 s + stagger)
  await p.waitForTimeout(3500); mark(`${k}_table`);
  if (k === 'true') { const ch = await p.$('#out .chain'); if (ch) { await p.evaluate(e => e.scrollIntoView({ behavior: 'smooth', block: 'center' }), ch); await p.waitForTimeout(3000); mark('true_chain'); } }
  await p.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' })); await p.waitForTimeout(800);
  await p.click('#photo-x');
}
const fw = await failed(); if (fw) console.log('WARNING: check this text on screen (model call failed or FAKE?):', fw);
mark('end');
await ctx.close(); await b.close();
fs.writeFileSync(out + '/marks.json', JSON.stringify(marks, null, 2));
console.log('video in', out);
