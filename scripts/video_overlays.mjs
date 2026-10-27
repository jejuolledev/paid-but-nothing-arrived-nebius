// Renders the stills and overlays for the Nebius video (this ffmpeg has no drawtext): subtitle strips for each
// narration line (docs/video/lines.json), the message / measured / architecture / title cards, and the live label.
// Output: docs/video/parts/*.png (1920x1080). Run: node scripts/video_overlays.mjs
import { chromium } from '/Users/ollekil/Desktop/Moahub-Labs/webs/알리기팔기작전/홍보엔진/node_modules/playwright/index.mjs';
import fs from 'node:fs';

const OUT = 'docs/video/parts'; fs.mkdirSync(OUT, { recursive: true });
const { lines } = JSON.parse(fs.readFileSync('docs/video/lines.json', 'utf8'));
const M = JSON.parse(fs.readFileSync('docs/video/measured.json', 'utf8'));
if (lines.some(l => l.text.startsWith('FILL'))) console.log('WARNING: a narration line still says FILL — edit docs/video/lines.json');
const split = s => { if (s.length < 110) return [s]; const mid = s.length / 2; let i = s.indexOf('. ', mid - 30); if (i < 0 || i > mid + 45) i = s.indexOf(' ', mid); return [s.slice(0, i + 1).trim(), s.slice(i + 1).trim()]; };
const esc = s => String(s).replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
const base = `<style>*{box-sizing:border-box}body{margin:0;background:transparent;font-family:-apple-system,"Inter","Segoe UI",sans-serif}</style>`;
const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
const shot = async (html, name, transparent = true) => { await p.setContent(base + html); await p.screenshot({ path: `${OUT}/${name}.png`, omitBackground: transparent }); };

const parts = {};
for (const l of lines) {
  parts[l.id] = split(l.text);
  for (const [j, t] of parts[l.id].entries())
    await shot(`<div style="position:absolute;left:0;right:0;bottom:46px;text-align:center"><span style="display:inline-block;max-width:1560px;background:rgba(8,10,14,.84);color:#fff;font-size:38px;line-height:1.32;font-weight:600;padding:12px 26px;border-radius:10px">${esc(t)}</span></div>`, `sub_${l.id}_${j}`);
}
fs.writeFileSync(`${OUT}/subs.json`, JSON.stringify(parts, null, 1));

await shot(`<div style="position:absolute;left:26px;top:22px;background:#0b2e1a;color:#9ff0bf;border:1px solid #1f7a45;font-size:24px;font-weight:700;padding:8px 14px;border-radius:8px">Live run · NVIDIA Nemotron on Nebius Token Factory · synthetic data</div>`, 'label_live');

const card = inner => `<div style="width:1920px;height:1080px;background:#0f1115;color:#e8eaf0;padding:170px 150px">${inner}</div>`;
await shot(card(`<div style="height:100%;display:flex;align-items:center;justify-content:center"><div style="width:900px;background:#1b1f27;border:2px solid #3a4352;border-radius:36px;padding:56px 60px">
<div style="font-size:26px;color:#9aa3b2">Customer · 1:04 AM</div>
<div style="font-size:52px;font-weight:700;line-height:1.3;margin-top:18px;color:#ff8a8c">“I paid 24,900 won and nothing arrived. I’m filing a chargeback.”</div></div></div>`), 'card_message', false);

const box = (t, d, c = '#3a4352') => `<div style="flex:1;border:2px solid ${c};border-radius:18px;padding:26px 24px;background:#151922"><div style="font-size:34px;font-weight:800">${t}</div><div style="font-size:24px;color:#aeb6c4;margin-top:10px;line-height:1.35">${d}</div></div>`;
const arrow = '<div style="font-size:48px;color:#5b8def;align-self:center">→</div>';
await shot(card(`<div style="font-size:30px;color:#9aa3b2;letter-spacing:.08em;text-transform:uppercase">How it works</div>
<div style="font-size:58px;font-weight:800;margin:14px 0 60px">The model reads and plans. Code decides.</div>
<div style="display:flex;gap:22px">${box('Message', 'addresses replaced, card digits removed')}${arrow}${box('Nemotron · Token Factory', 'who is writing, what they claim, which lookups', '#1f7a45')}${arrow}${box('Read-only lookups', 'only the sender’s own trail')}${arrow}${box('Verifier', 'marks the broken link, cites the rows', '#8a6417')}${arrow}${box('Nemotron · Token Factory', 'cited explanation + reply, checked sentence by sentence', '#1f7a45')}</div>
<div style="font-size:28px;color:#9aa3b2;margin-top:56px">Fixes run only after the seller clicks Approve.</div>`), 'card_arch', false);

const stat = (n, t) => `<div style="flex:1;border:2px solid #2a2f3a;border-radius:18px;padding:30px 34px"><div style="font-size:84px;font-weight:800;color:#7ee2a8">${esc(n)}</div><div style="font-size:30px;color:#c3c9d4;margin-top:8px">${t}</div></div>`;
await shot(card(`<div style="font-size:30px;color:#9aa3b2;letter-spacing:.08em;text-transform:uppercase">Measured</div>
<div style="font-size:58px;font-weight:800;margin:14px 0 46px">${M.held_out_n} messy messages written by a separate model</div>
<div style="display:flex;gap:34px">${stat(M.model_end_to_end, 'right order and broken link, with Nemotron reading the message')}${stat(M.rules_end_to_end, 'the same, with rules only')}${stat(M.complaint, 'complaint read correctly')}</div>
<div style="font-size:26px;color:#9aa3b2;margin-top:40px">Model: ${esc(M.model_id)} on Nebius Token Factory · values the message did not support and were dropped: ${esc(M.dropped_values)} · avg model time per message: ${esc(M.avg_ms)} ms · all data synthetic</div>`), 'card_measured', false);

await shot(card(`<div style="height:100%;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center">
<div style="font-size:96px;font-weight:800">Paid, but nothing arrived?</div><div style="font-size:52px;color:#7ee2a8;margin-top:18px">Found in one pass.</div>
<div style="font-size:30px;color:#9aa3b2;margin-top:60px">NVIDIA Nemotron on Nebius Token Factory</div>
<div style="font-size:26px;color:#6f7888;margin-top:16px">TRY_IT_URL · all data synthetic · MIT</div></div>`.replace('TRY_IT_URL', esc(process.env.TRY_URL || 'live demo link in the description'))), 'card_title', false);
await b.close(); console.log('overlays ok');
