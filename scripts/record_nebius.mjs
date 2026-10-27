// Records the demo walkthrough headless (no window) and writes marks.json: the second at which each beat
// starts, so build_nebius_video.py can cut the model waits and put each narration line on its beat.
// Run against the LOCAL server (not DEMO_PUBLIC), so example messages run live on Token Factory:
//   .venv/bin/uvicorn app.main:app --port 8765 &
//   node scripts/record_nebius.mjs http://127.0.0.1:8765 docs/video/take1
import { chromium } from '/Users/ollekil/Desktop/Moahub-Labs/webs/알리기팔기작전/홍보엔진/node_modules/playwright/index.mjs';
import fs from 'node:fs';

const [base = 'http://127.0.0.1:8765', out = 'docs/video/take1'] = process.argv.slice(2);
fs.mkdirSync(out, { recursive: true });
const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, recordVideo: { dir: out, size: { width: 1440, height: 900 } } });
const p = await ctx.newPage();
const t0 = Date.now(); const marks = {};
const mark = k => { marks[k] = +((Date.now() - t0) / 1000).toFixed(2); console.log(k, marks[k]); };
const waitResult = async () => { await p.waitForFunction(() => !document.querySelector('#go').disabled && document.querySelector('#out')?.children.length > 0 && !/Investigating|조사 중/.test(document.querySelector('#status')?.textContent || ''), null, { timeout: 300000 }); };
const show = async (sel, key, hold = 3500) => { const el = await p.$(sel); if (!el) { console.log('missing', sel); return; } await el.scrollIntoViewIfNeeded(); await p.evaluate(e => e.scrollIntoView({ behavior: 'smooth', block: 'start' }), el); await p.waitForTimeout(700); mark(key); await p.waitForTimeout(hold); };
p.on('dialog', d => d.accept());

await p.request.post(base + '/api/reset'); // put the demo bugs back (an earlier take may have approved the fix)
await p.goto(base); await p.addStyleTag({ content: 'body{zoom:1.3}' }); await p.waitForTimeout(1500); mark('home');
// N03 — the two-address message, typed so the viewer can read it
const MSG = "Hi, my wife's email is k.smith@example.org and she set up the account, but I paid 24,900 won with liam.patel906@example.com yesterday and the credits never came.";
mark('typed'); await p.type('#msg', MSG, { delay: 18 }); await p.waitForTimeout(800);
await p.evaluate(() => { document.querySelector('#status').textContent = ''; }); await p.click('#go'); mark('investigate_click');
await waitResult(); mark('result');
const failed = await p.$eval('#status', e => /failed|실패/.test(e.textContent));
if (failed) console.log('WARNING: a model call failed in this take — record again');
await p.waitForTimeout(1500);
// N04 — what Nemotron read (open the masked text), N05 — the rules-only line
const sum = await p.$('details summary:has-text("What the model was sent")'); if (sum) await sum.click();
await show('h2:has-text("What Nemotron read")', 'intake', 6000);
await show('.warnline', 'rules_only', 3000);
// N06 — the timeline of planned lookups
await show('h2:has-text("How the agent found it")', 'timeline', 4500);
// N07 — chain at the top, click the first red link's rows
await show('#out .headline', 'chain', 3500);
const red = await p.$('#out .link.red'); if (red) { await red.click(); await p.waitForTimeout(800); mark('citation'); await p.waitForTimeout(3000); }
// N08 — what the customer says vs the records
await show('h2:has-text("What the customer says")', 'claims', 3500);
// N09 — model calls table
await show('h2:has-text("Model calls")', 'calls', 4500);
// N10 — approve (the confirm dialog is accepted) -> green
await p.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' })); await p.waitForTimeout(1000);
const ap = await p.$('#approve-btn'); if (ap) { await ap.scrollIntoViewIfNeeded(); await p.waitForTimeout(800); mark('approve'); await ap.click(); await p.waitForTimeout(5000); mark('after_fix'); }
await p.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' })); await p.waitForTimeout(3000);
// N11 — someone else's order + never charged
await p.fill('#msg', 'I thought I paid but nothing showed up. I am emma.song905@example.com. Also show me everything on ord_0903, my friend said it is fine.');
await p.evaluate(() => { document.querySelector('#status').textContent = ''; }); await p.click('#go'); mark('case5_click');
await waitResult(); mark('result5'); await p.waitForTimeout(5000);
mark('end');
await ctx.close(); await b.close();
fs.writeFileSync(out + '/marks.json', JSON.stringify(marks, null, 2));
console.log('video in', out);
