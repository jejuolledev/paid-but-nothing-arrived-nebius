// Headless render of phone-screen HTML files to PNG.
// usage: node render.mjs jobs.json
// jobs.json: [{ "html": "/abs/x.html", "png": "/abs/x.png", "boxes": "/abs/x.boxes.json" }]
// Writes each PNG at 390x844 CSS px, deviceScaleFactor 2, plus the bounding
// boxes (device px) of every element with class "ef" (editable fields).
import { chromium } from '/Users/ollekil/Desktop/Moahub-Labs/webs/알리기팔기작전/홍보엔진/node_modules/playwright/index.mjs';
import { readFileSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const DSF = 2;
const jobs = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: DSF });
const page = await ctx.newPage();
for (const j of jobs) {
  await page.goto(pathToFileURL(j.html).href, { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: j.png, fullPage: false });
  const boxes = await page.evaluate(() => {
    const out = {};
    for (const el of document.querySelectorAll('.ef')) {
      const r = el.getBoundingClientRect();
      out[el.id] = [r.left, r.top, r.right, r.bottom];
    }
    // detect overflow (content cut off below the screen)
    out.__overflow = document.documentElement.scrollHeight > 844 + 1;
    return out;
  });
  for (const k of Object.keys(boxes)) if (Array.isArray(boxes[k])) boxes[k] = boxes[k].map(v => Math.round(v * DSF));
  writeFileSync(j.boxes, JSON.stringify(boxes));
}
await browser.close();
console.log(`rendered ${jobs.length}`);
