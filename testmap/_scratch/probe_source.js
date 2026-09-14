/* 探测页面用的是哪份数据源。用法: node probe_source.js <url> */
const PW = 'C:/Users/jingy/AppData/Roaming/npm/node_modules/@playwright/cli/node_modules/playwright-core';
const CHROME = process.env.LOCALAPPDATA + '/ms-playwright/chromium-1243/chrome-win64/chrome.exe';

(async () => {
  const { chromium } = require(PW);
  const browser = await chromium.launch({
    executablePath: CHROME, args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  const page = await browser.newPage();
  const errs = [], failed = [], ok200 = [];
  page.on('pageerror', e => errs.push(String(e).slice(0, 160)));
  page.on('requestfailed', r => failed.push(r.url().slice(0, 110) + ' -> ' + (r.failure() || {}).errorText));
  page.on('response', r => { if (r.status() >= 400) failed.push('HTTP ' + r.status() + ' ' + r.url().slice(0, 110)); });
  await page.goto(process.argv[2], { waitUntil: 'load', timeout: 60000 });
  await page.waitForTimeout(4000);
  await page.evaluate(() => performance.getEntriesByType('resource')
    .forEach(r => window.__res = (window.__res || [])));
  const r = await page.evaluate(() => {
    const f = window.XT && window.XT.frames;
    return {
      src: window.__XT_SRC || '(未设置)',
      frames: f ? f.length : 0,
      last: f && f.length ? f[f.length - 1].time : null,
      bakedLiteralPresent: document.documentElement.innerHTML.indexOf('SINGLE_HTML_BAKED_DATA') >= 0,
      tagMap: (document.getElementById('tagMap') || {}).textContent,
    };
  });
  r.failedRequests = failed;
  r.pageErrors = errs;
  console.log(JSON.stringify(r, null, 2));
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
