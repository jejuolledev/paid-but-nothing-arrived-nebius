// YouTube thumbnail (1280x720): the detective-robot comic panel, the question, and the broken chain.
import { chromium } from '/Users/ollekil/Desktop/Moahub-Labs/webs/알리기팔기작전/홍보엔진/node_modules/playwright/index.mjs';
import path from 'node:path';
import fs from 'node:fs';
const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const bg = 'file://' + path.join(ROOT, 'docs/comic/raw/P4_b.png');
const html = `<!doctype html><meta charset="utf-8"><style>
*{box-sizing:border-box;margin:0}body{width:1280px;height:720px;overflow:hidden;font-family:-apple-system,"Inter",sans-serif;background:#0e1116}
.bg{position:absolute;inset:0;background:url('${bg}') center/cover}
.shade{position:absolute;inset:0;background:linear-gradient(90deg,rgba(8,10,14,.94) 0%,rgba(8,10,14,.82) 46%,rgba(8,10,14,0) 72%)}
.t{position:absolute;left:56px;top:70px;width:720px;color:#fff}
.q{font-size:86px;font-weight:900;line-height:1.0;letter-spacing:-1.5px}
.q span{color:#ff6b61}
.s{margin-top:22px;font-size:38px;font-weight:700;color:#cfe9ff}
.chain{position:absolute;left:56px;bottom:118px;display:flex;gap:12px}
.l{width:120px;height:58px;border-radius:14px;border:4px solid;display:flex;align-items:center;justify-content:center;font-size:30px;font-weight:900}
.g{border-color:#3fb97d;color:#7ee2a8;background:rgba(17,38,28,.9)}.r{border-color:#ff5a50;color:#ff8a82;background:rgba(43,21,19,.92)}
.tags{position:absolute;left:56px;bottom:46px;display:flex;gap:10px}
.tag{font-size:22px;font-weight:800;padding:7px 14px;border-radius:999px;background:rgba(8,10,14,.85);border:2px solid #3a4352;color:#e8edf5}
</style><div class="bg"></div><div class="shade"></div>
<div class="t"><div class="q">Paid, but<br><span>nothing</span> arrived?</div><div class="s">An AI agent finds the broken link — with proof.</div></div>
<div class="chain"><div class="l g">✓</div><div class="l g">✓</div><div class="l g">✓</div><div class="l r">✕</div><div class="l r">✕</div></div>
<div class="tags"><span class="tag">Zetaris</span><span class="tag">Meterless Nightshift</span><span class="tag">NVIDIA Nemotron</span><span class="tag">Cursor</span></div>`;
const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1280, height: 720 } });
// a file:// page, so the local background image may load (setContent is about:blank and blocks it)
const tmp = path.join(ROOT, 'docs/demo/_thumb.html'); fs.writeFileSync(tmp, html);
await p.goto('file://' + tmp); await p.waitForTimeout(600); fs.unlinkSync(tmp);
await p.screenshot({ path: path.join(ROOT, 'docs/demo/thumbnail.png') }); await b.close(); console.log('thumbnail ok');
