/* 验证单文件 HTML：file:// 打开、外部请求清单、控制台、256 对拍数值。
   用法: node verify_single.js <html路径> <online|offline> <截图路径> */
const path = require('path');
const PW = 'C:/Users/jingy/AppData/Roaming/npm/node_modules/@playwright/cli/node_modules/playwright-core';

const file = process.argv[2];
const mode = process.argv[3] || 'online';
const shot = process.argv[4];
const CHROME = process.env.LOCALAPPDATA + '/ms-playwright/chromium-1243/chrome-win64/chrome.exe';

(async () => {
  const { chromium } = require(PW);
  const browser = await chromium.launch({
    executablePath: CHROME,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();

  const reqs = [], console_msgs = [], page_errors = [];
  page.on('request', r => reqs.push(r.url()));
  page.on('console', m => console_msgs.push('[' + m.type() + '] ' + m.text().slice(0, 200)));
  page.on('pageerror', e => page_errors.push(String(e).slice(0, 300)));

  if (mode === 'offline') {
    // 拦掉高德，模拟断网 / Key 失效
    await ctx.route('**://*.amap.com/**', r => r.abort());
    await ctx.route('**://webapi.amap.com/**', r => r.abort());
    await ctx.route('**://*.autonavi.com/**', r => r.abort());
  }

  await page.goto('file:///' + file.replace(/\\/g, '/'), { waitUntil: 'load', timeout: 60000 });

  // 等底图就绪或退回兜底
  try {
    await page.waitForFunction(
      () => /已就绪|底图不可用/.test((document.getElementById('tagMap') || {}).textContent || ''),
      { timeout: mode === 'offline' ? 25000 : 20000 }
    );
  } catch (e) {
    console.log('  !! 等待底图状态超时');
  }

  // 等 256 对拍算完
  try {
    await page.waitForFunction(
      () => (document.getElementById('refAgree') || {}).textContent !== '—',
      { timeout: 15000 }
    );
  } catch (e) { /* 记到下面的读数里 */ }

  await page.waitForTimeout(2500);

  const state = await page.evaluate(() => {
    const g = id => { const e = document.getElementById(id); return e ? e.textContent.trim() : null; };
    const im = document.getElementById('refImg');
    const requests = performance.getEntriesByType('resource').map(r => r.name);
    return {
      tagMap: g('tagMap'), clock: g('clock'), dateStr: g('dateStr'),
      grid: g('mGrid'), range: g('mRange'), poly: g('mPoly'),
      refAgree: g('refAgree'), refMissing: g('refMissing'),
      refImgLoaded: !!(im && im.complete && im.naturalWidth === 256),
      refDim: g('refDim'),
      legendRows: document.querySelectorAll('#legend .lg').length,
      frames: window.XT ? window.XT.frames.length : 0,
      selfContained: window.XT ? !!window.XT.selfContained : false,
      fallbackOn: document.getElementById('fallback').classList.contains('on'),
      whiteWrapVisible: getComputedStyle(document.getElementById('whiteWrap')).display !== 'none',
      resourceRequests: requests,
    };
  });

  // 切到下一帧，确认联动
  await page.click('#next');
  await page.waitForTimeout(2500);
  const after = await page.evaluate(() => ({
    clock: document.getElementById('clock').textContent.trim(),
    poly: document.getElementById('mPoly').textContent.trim(),
    refAgree: document.getElementById('refAgree').textContent.trim(),
  }));

  if (shot) await page.screenshot({ path: shot });

  const localRefs = reqs.filter(u => /\.(js|png|css)(\?|$)/.test(u) && !/^data:/.test(u));
  const netReqs = reqs.filter(u => !/^data:/.test(u) && !/^file:/.test(u));

  console.log('===== 模式: ' + mode + ' =====');
  console.log('tagMap        :', state.tagMap);
  console.log('兜底视图是否显示:', state.fallbackOn);
  console.log('帧数          :', state.frames, ' selfContained:', state.selfContained);
  console.log('图例行数      :', state.legendRows);
  console.log('白色档开关可见:', state.whiteWrapVisible);
  console.log('--- 帧 1 ---');
  console.log('时刻          :', state.clock, state.dateStr);
  console.log('网格 / 等值面 :', state.grid, '/', state.poly);
  console.log('数值范围      :', state.range);
  console.log('256 图已加载  :', state.refImgLoaded, '(' + state.refDim + ')');
  console.log('与主视图一致  :', state.refAgree, ' 未被覆盖:', state.refMissing);
  console.log('--- 切到帧 2 后 ---');
  console.log('时刻          :', after.clock, ' 等值面:', after.poly, ' 一致度:', after.refAgree);
  console.log('--- 请求 ---');
  console.log('非 file/data 的请求 (' + netReqs.length + '):');
  netReqs.slice(0, 12).forEach(u => console.log('   ', u.slice(0, 130)));
  console.log('本地附件请求 (应为 0):', localRefs.length);
  localRefs.slice(0, 10).forEach(u => console.log('   !!', u.slice(0, 130)));
  console.log('控制台 (' + console_msgs.length + '):');
  console_msgs.slice(0, 6).forEach(m => console.log('   ', m));
  console.log('页面错误 (' + page_errors.length + '):');
  page_errors.slice(0, 6).forEach(m => console.log('   !!', m));

  await browser.close();
})().catch(e => { console.error('验证脚本出错:', e); process.exit(1); });
