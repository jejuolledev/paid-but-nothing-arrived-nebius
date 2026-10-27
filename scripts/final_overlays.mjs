// Renders the stills and overlays for the final video (ffmpeg here has no drawtext/subtitles):
// subtitle strips per narration line, the sponsor badge, the measurements card, the title card and small labels.
// Output: docs/demo/final_parts/*.png (1920x1080 or transparent strips).
import { chromium } from '/Users/ollekil/Desktop/Moahub-Labs/webs/알리기팔기작전/홍보엔진/node_modules/playwright/index.mjs';
import fs from 'node:fs';

const OUT = 'docs/demo/final_parts'; fs.mkdirSync(OUT, { recursive: true });
const LINES = {
  N01: '“I paid 24,900 won and nothing arrived. I’m filing a chargeback.” Every small online seller knows this message.',
  N02: 'The proof is in four places: the payment provider, the orders database, the server logs, the mail provider. At one in the morning, that’s four dashboards.',
  N03: 'Paste the message. Just the customer’s email — no order number.',
  N04: 'Nemotron, through Meterless Nightshift, decides where to look. No order under this email. So: who paid at the payment provider? Which order does that payment belong to? Then the full journey. Every lookup is read-only, through one SQL door — Zetaris.',
  N05: 'A rule-based verifier — not the model — checks the money chain. Paid. Order confirmed. But the credits went to a typo — exmaple dot com — and the mail bounced. Every red link carries the rows that prove it, and the one query that fetched them.',
  N05b: 'And the model’s explanation is checked sentence by sentence: every amount, address and status it states must match the rows it cites.',
  N06: 'You get a reply in the customer’s language. It can’t promise refunds — money is a human decision. And a fix: move the credits, once the customer confirms.',
  N07: 'Approve, and the fix runs. The chain turns green, and the fix goes into an audit log.',
  N08: 'And when nothing is broken, it says so: you were never charged.',
  N08b: 'And if a message quotes someone else’s order number, that order is never read.',
  N09: 'Under the hood: the shop database, the payment provider’s ledger and the mail provider’s events are three separate sources in Zetaris, joined in one semantic layer and read with a single query. Every model call goes through Nightshift, with a receipt for which model ran. Addresses are masked and card digits removed before any row reaches the model.',
  N10: 'Six cases, rebuilt from real bugs in our own shop with synthetic data: the right order and broken link, six out of six, on every run. And on wrong sentences written by a separate model that never saw the checker, it caught thirty-two of forty.',
  N11: 'Paid, but nothing arrived? Found in one pass.',
};
// long lines are split into two halves so a strip never holds more than two rows
const split = s => { if (s.length < 110) return [s]; const mid = s.length / 2; let i = s.indexOf('. ', mid - 25); if (i < 0 || i > mid + 40) i = s.indexOf(' ', mid); return [s.slice(0, i + 1).trim(), s.slice(i + 1).trim()]; };

const base = `<style>*{box-sizing:border-box}body{margin:0;background:transparent;font-family:-apple-system,"Inter","Segoe UI",sans-serif}</style>`;
const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
const shot = async (html, name, transparent = true) => { await p.setContent(base + html); await p.screenshot({ path: `${OUT}/${name}.png`, omitBackground: transparent }); };

const parts = {};
for (const [k, s] of Object.entries(LINES)) {
  parts[k] = split(s);
  for (const [j, t] of parts[k].entries())
    await shot(`<div style="position:absolute;left:0;right:0;bottom:46px;text-align:center"><span style="display:inline-block;max-width:1500px;background:rgba(8,10,14,.82);color:#fff;font-size:38px;line-height:1.32;font-weight:600;padding:12px 26px;border-radius:10px">${t}</span></div>`, `sub_${k}_${j}`);
}
fs.writeFileSync(`${OUT}/subs.json`, JSON.stringify(parts, null, 1));

await shot(`<div style="position:absolute;right:26px;top:22px;display:flex;gap:8px">${['Zetaris', 'Meterless Nightshift', 'NVIDIA Nemotron', 'built with Cursor'].map(x => `<span style="background:rgba(8,10,14,.78);color:#dfe6f2;border:1px solid #3a4352;font-size:20px;font-weight:600;padding:6px 12px;border-radius:999px">${x}</span>`).join('')}</div>`, 'badges');
await shot(`<div style="position:absolute;left:26px;top:22px;background:#3b2a07;color:#ffd98a;border:1px solid #8a6417;font-size:24px;font-weight:700;padding:8px 14px;border-radius:8px">Offline demo · same data on DuckDB · on Zetaris the agent is read-only; fixes are applied in your own systems</div>`, 'label_offline');
await shot(`<div style="position:absolute;left:26px;top:22px;background:#0b2e1a;color:#9ff0bf;border:1px solid #1f7a45;font-size:24px;font-weight:700;padding:8px 14px;border-radius:8px">Live run · data through Zetaris (local platform) · model: Nemotron 3.5 Lightning via Nightshift</div>`, 'label_live');

const card = (inner) => `<div style="width:1920px;height:1080px;background:#0f1115;color:#e8eaf0;padding:200px 150px">${inner}</div>`;
await shot(card(`<div style="font-size:30px;color:#9aa3b2;letter-spacing:.08em;text-transform:uppercase">Measured</div>
<div style="font-size:64px;font-weight:800;margin:16px 0 50px">6 cases from our own shop, synthetic data</div>
<div style="display:flex;gap:40px">${[['6 / 6', 'right order and right broken link, in every one of six runs on Zetaris'], ['32 / 40', 'wrong sentences caught, written by a model that never saw the checker'], ['24', 'automated tests']].map(([n, t]) => `<div style="flex:1;border:2px solid #2a2f3a;border-radius:18px;padding:34px 36px"><div style="font-size:92px;font-weight:800;color:#7ee2a8">${n}</div><div style="font-size:32px;color:#c3c9d4;margin-top:8px">${t}</div></div>`).join('')}</div>
<div style="font-size:28px;color:#9aa3b2;margin-top:46px">Six runs on the local Zetaris platform (three datasources, one query per order), Nightshift → NVIDIA Nemotron 3.5 Lightning (hosted, free key). A message quoting another customer’s order was refused in every run. When a sentence fails the check, the verifier’s text is shown instead.</div>`), 'card_measured', false);
await shot(card(`<div style="height:100%;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center">
<div style="font-size:96px;font-weight:800">Paid, but nothing arrived?</div><div style="font-size:52px;color:#7ee2a8;margin-top:18px">Found in one pass.</div>
<div style="font-size:30px;color:#9aa3b2;margin-top:60px">Zetaris · Meterless Nightshift · NVIDIA Nemotron · built with Cursor</div>
<div style="font-size:26px;color:#6f7888;margin-top:16px">github.com/jejuolledev/paid-but-nothing-arrived · all data synthetic</div></div>`), 'card_title', false);
await b.close(); console.log('overlays ok');
