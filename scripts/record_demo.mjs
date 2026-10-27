// Records the demo walkthrough headlessly with Playwright: 1280x720 video + screenshots per case.
// Usage: node scripts/record_demo.mjs [http://127.0.0.1:8765]
// Output: docs/demo/walkthrough.webm, docs/demo/case-N.png. Captions are injected as a bottom banner
// so the cut needs no voice-over; a subtitle file (SRT) with the same lines is written alongside.
import { chromium } from '/Users/ollekil/Desktop/Moahub-Labs/webs/알리기팔기작전/홍보엔진/node_modules/playwright/index.mjs';
import fs from 'node:fs';
import path from 'node:path';

const base = process.argv[2] || 'http://127.0.0.1:8765';
const out = path.resolve('docs/demo'); fs.mkdirSync(out, { recursive: true });
const steps = [
  { id: 'ord_0901', hold: 9, caption: '"I paid, but nothing arrived." — every online seller gets this message. The agent asks one SQL door (Zetaris) across the PSP ledger, orders, grants, server logs and mail events.' },
  { id: 'ord_0901', hold: 7, caption: 'Case 1 — the PSP says PAID, our order row says failed. The chain breaks at "Order confirmed", and the raw rows that prove it are one click away.' },
  { id: 'ord_0902', hold: 7, caption: 'Case 2 — paid, but the confirm call never arrived. Same symptom for the customer, different broken link, different evidence.' },
  { id: 'ord_0903', hold: 7, caption: 'Case 3 — the customer got the credits twice. Two grant rows, one timeout, one manual retry.' },
  { id: 'ord_0904', hold: 7, caption: 'Case 4 — credits granted, mail never sent. The customer has them and does not know. Reply draft, fix (needs approval), dispute evidence bundle.' },
  { id: 'ord_0905', hold: 8, caption: 'Case 5 — nothing is broken. You were never charged. The agent can say so, with evidence.' },
];
const srt = [];
let t = 0;
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 }, recordVideo: { dir: out, size: { width: 1280, height: 720 } }, colorScheme: 'dark' });
const page = await ctx.newPage();
await page.goto(base, { waitUntil: 'networkidle' });
await page.addStyleTag({ content: '#cap{position:fixed;left:0;right:0;bottom:0;background:rgba(0,0,0,.82);color:#fff;font:600 20px/1.35 -apple-system,Inter,sans-serif;padding:14px 28px;z-index:9999;border-top:2px solid #5b8def}' });
await page.evaluate(() => { const d = document.createElement('div'); d.id = 'cap'; document.body.appendChild(d); });
const fmt = s => new Date(s * 1000).toISOString().substr(11, 12).replace('.', ',');
let n = 0;
for (const s of steps) {
  n++;
  await page.fill('#msg', `Hi, I paid but nothing arrived. My order is ${s.id}.`);
  await page.evaluate(() => { document.getElementById('out').innerHTML = ''; });
  await page.click('#go');
  await page.waitForSelector('.link', { timeout: 60000 });
  await page.waitForFunction(() => /ms ·/.test(document.getElementById('status').textContent), null, { timeout: 60000 });
  await page.evaluate(c => { document.getElementById('cap').textContent = c; }, s.caption);
  await page.waitForTimeout(800);
  await page.screenshot({ path: path.join(out, `case-${n}.png`) });
  srt.push(`${srt.length + 1}\n${fmt(t)} --> ${fmt(t + s.hold)}\n${s.caption}\n`);
  if (n === 1) { await page.evaluate(() => document.querySelector('.link.red,.link.grey')?.click()); }
  if (n === 5) { await page.waitForTimeout(2500); await page.evaluate(() => window.scrollTo(0, 420)); }
  await page.waitForTimeout(s.hold * 1000);
  await page.evaluate(() => window.scrollTo(0, 0));
  t += s.hold;
}
await ctx.close(); await browser.close();
const vids = fs.readdirSync(out).filter(f => f.endsWith('.webm') && f !== 'walkthrough.webm');
if (vids.length) fs.renameSync(path.join(out, vids[0]), path.join(out, 'walkthrough.webm'));
fs.writeFileSync(path.join(out, 'captions.srt'), srt.join('\n'));
console.log('recorded', t, 'seconds ->', path.join(out, 'walkthrough.webm'));
