// Renders the title and architecture cards (1280x720 PNG) with headless Chromium — ffmpeg here has no drawtext.
import { chromium } from '/Users/ollekil/Desktop/Moahub-Labs/webs/알리기팔기작전/홍보엔진/node_modules/playwright/index.mjs';
import fs from 'node:fs';
const out = 'docs/demo'; fs.mkdirSync(out, { recursive: true });
const css = `<style>body{margin:0;width:1280px;height:720px;background:#0f1115;color:#e8eaf0;font:26px/1.45 -apple-system,Inter,Segoe UI,sans-serif;padding:72px 90px;box-sizing:border-box}
h1{font-size:40px;margin:0 0 26px;line-height:1.2}p{color:#c3c9d4;margin:0 0 16px}b{color:#fff}.q{font-size:34px;color:#fff;margin-bottom:22px}.tag{display:inline-block;border:1px solid #2a2f3a;border-radius:999px;padding:2px 12px;font-size:18px;color:#9aa3b2;margin-top:10px}
.row{display:flex;gap:22px;margin-top:8px}.box{flex:1;border:2px solid #2a2f3a;border-radius:12px;padding:14px 16px;font-size:21px}.box b{display:block;font-size:23px;margin-bottom:6px}</style>`;
const cards = {
  intro: `${css}<div class="q">“I paid, but nothing arrived.”</div><h1>Paid, but nothing arrived — the agent that finds the broken link</h1>
<p>Every online seller gets this message. A slow answer becomes a card dispute — and the evidence is spread over four systems: the payment provider, the orders database, the server logs, the mail provider.</p>
<p>This agent asks <b>one SQL door (Zetaris)</b>, walks the money chain, marks the one link that broke — with the raw rows that prove it — and a <b>local Nemotron on Meterless Nightshift</b> explains. Customer data never leaves the machine.</p>
<span class="tag">Track 02 — The Agent That Can Explain Why</span> <span class="tag">all data synthetic</span>`,
  arch: `${css}<h1>How it is built</h1>
<div class="row"><div class="box"><b>Zetaris — one SQL door</b>payments · orders · grants · server_logs · mail_events (one Postgres datasource) activated into the semantic layer <i>order_journey</i>. The agent sends SQL only; every row carries <i>table:key</i>.</div>
<div class="box"><b>Meterless Nightshift + NVIDIA Nemotron</b>Local OpenAI-compatible runtime. Nemotron 3.5 Lightning explains, drafts the reply, phrases the fix — it never decides. Every sentence must cite a returned ref or it is rejected.</div></div>
<div class="row"><div class="box"><b>Verifier decides</b>Deterministic five-link check: green / red / grey with refs. The model cannot override it. Fixes need human approval.</div>
<div class="box"><b>Cursor</b>Project rules in <i>.cursor/rules</i>, agent sessions in <i>docs/cursor-sessions</i>.</div></div>
<p style="margin-top:22px">Next: real PSP and mail connectors as Zetaris REST sources · receipt-screenshot reading with a local vision model · installable edition for sellers.</p>`,
};
const browser = await chromium.launch(); const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
for (const [name, html] of Object.entries(cards)) { await page.setContent(html); await page.screenshot({ path: `${out}/_${name}.png` }); }
await browser.close(); console.log('cards ok');
