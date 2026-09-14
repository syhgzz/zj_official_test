
(function () {
  'use strict';
  var XT = window.XT;
  if (!XT) { document.body.innerHTML = '<p style="padding:24px">没拿到 window.XT，页面数据没加载上。'
    + '单文件版请用 build_single_html.py 重新生成；拆文件版请确认 data.js 与页面同目录，并通过 HTTP 访问。</p>'; return; }

  var $ = function (id) { return document.getElementById(id); };
  var cur = 0, map = null, AMapNS = null, overlay = null;
  var Z_BASE = 1, Z_OVER = 10;
  var REF_SIZE = (XT.referenceSize || 256);

  function frame() { return XT.frames[cur]; }

  /* ---------------- 底图 ---------------- */
  function fitZoom(bbox) {
    var z = 4;
    for (var i = 4; i <= 17; i++) {
      var scale = Math.pow(2, i);
      var span = (bbox[2] - bbox[0]) / 360 * 256 * scale;
      if (span > window.innerWidth * 0.85) break;
      z = i;
    }
    return z;
  }
  function loadAmap() {
    var cfg = window.WMTS_MAP_CONFIG;
    if (!cfg || !cfg.amap || !cfg.amap.key) return Promise.reject(new Error('缺少高德 Key'));
    window._AMapSecurityConfig = { securityJsCode: cfg.amap.securityJsCode };
    var key = cfg.amap.key;
    return new Promise(function (resolve, reject) {
      var cb = 'initAmap_' + Date.now();
      var s = document.createElement('script');
      var done = false;
      var timer = setTimeout(function () { fin(new Error('高德加载超时（Key 白名单/网络）')); }, 15000);
      function fin(err) {
        if (done) return; done = true; clearTimeout(timer); delete window[cb];
        if (err) reject(err); else if (window.AMap) resolve(window.AMap);
        else reject(new Error('AMap 对象不可用'));
      }
      window[cb] = function () { fin(); };
      s.onload = function () { fin(); };
      s.onerror = function () { fin(new Error('高德脚本加载失败')); };
      s.src = 'https://webapi.amap.com/maps?v=2.0&key=' + encodeURIComponent(key)
            + '&callback=' + encodeURIComponent(cb);
      document.head.appendChild(s);
    });
  }

  /* ---------------- 离线兜底视图 ---------------- */
  function buildFallbackBase() {
    var view = XT.view, VW = view[2] - view[0], VH = view[3] - view[1];
    var latMid = (view[1] + view[3]) / 2;
    var wKm = VW * 111.32 * Math.cos(latMid * Math.PI / 180), hKm = VH * 110.57;
    var wrap = $('mapWrap'), st = $('fbStage');
    var s = Math.min((wrap.clientWidth - 44) / wKm, (wrap.clientHeight - 44) / hKm);
    st.style.width = Math.round(wKm * s) + 'px';
    st.style.height = Math.round(hKm * s) + 'px';

    var NS = 'http://www.w3.org/2000/svg', svg = $('fbSvg');
    svg.setAttribute('viewBox', '0 0 1000 ' + (1000 * VH / VW));
    var H = 1000 * VH / VW;
    svg.innerHTML = '';
    function el(n, a) { var e = document.createElementNS(NS, n); for (var k in a) e.setAttribute(k, a[k]); return e; }
    function frange(a, b, st2) { var o = [], v = Math.ceil(a / st2) * st2; for (; v <= b + 1e-9; v += st2) o.push(v); return o; }
    var sx = 1000 / VW, sy = H / VH;
    frange(view[0], view[2], 0.5).forEach(function (lon) {
      var x = (lon - view[0]) * sx;
      svg.appendChild(el('line', { x1: x, y1: 0, x2: x, y2: H, stroke: 'rgba(255,255,255,.14)', 'stroke-width': 1 }));
      var t = el('text', { x: x + 4, y: 13, fill: 'rgba(255,255,255,.45)', 'font-size': 12 });
      t.textContent = lon.toFixed(1) + '°E'; svg.appendChild(t);
    });
    frange(view[1], view[3], 0.5).forEach(function (lat) {
      var y = (view[3] - lat) * sy;
      svg.appendChild(el('line', { x1: 0, y1: y, x2: 1000, y2: y, stroke: 'rgba(255,255,255,.14)', 'stroke-width': 1 }));
      var t = el('text', { x: 5, y: y - 4, fill: 'rgba(255,255,255,.45)', 'font-size': 12 });
      t.textContent = lat.toFixed(1) + '°N'; svg.appendChild(t);
    });
    var d = '';
    (XT.boundary || []).forEach(function (ring) {
      ring.forEach(function (p, i) {
        d += (i ? 'L' : 'M') + ((p[0] - view[0]) * sx).toFixed(1) + ' ' + ((view[3] - p[1]) * sy).toFixed(1);
      });
      d += 'Z';
    });
    if (d) svg.appendChild(el('path', { d: d, fill: 'none', stroke: 'rgba(255,255,255,.8)',
                                       'stroke-width': 2, 'stroke-linejoin': 'round' }));
    setupFallbackImg();
  }
  function setupFallbackImg() {
    var view = XT.view, VW = view[2] - view[0], VH = view[3] - view[1];
    var f = frame(), b = f.bbox, im = $('fbRaster');
    im.src = currentPng(f);
    im.style.left = ((b[0] - view[0]) / VW * 100) + '%';
    im.style.top = ((view[3] - b[3]) / VH * 100) + '%';
    im.style.width = ((b[2] - b[0]) / VW * 100) + '%';
    im.style.height = ((b[3] - b[1]) / VH * 100) + '%';
  }

  /* ---------------- 覆盖层 ---------------- */
  function useWhite() { return $('whiteChk').checked; }
  function currentPng(f) {
    return (useWhite() && f.pngWhite) ? f.pngWhite : f.png;
  }

  /* ---------------- 参考原尺寸对拍 ----------------
     同一份等值面多边形，分别按参考代码的 256×256 和主视图的 1024×1024 渲染。
     把 1024 那张缩到 256 再逐像素比：几何一致的话应当基本重合，差异只来自
     边缘抗锯齿。所以比"分类结果"而不是比 RGB —— 按像素离哪个色阶最近归类，
     再统计两图分类不同的比例，这样不会被边缘那一个像素的插值差异放大。 */
  function classify(data, colors) {
    var n = data.length / 4, out = new Uint8Array(n);
    var cr = [], cg = [], cb = [], ca = [];
    for (var i = 0; i < colors.length; i++) {
      var h = String(colors[i] || '#000000').replace('#', '');
      cr.push(parseInt(h.slice(0, 2), 16) || 0);
      cg.push(parseInt(h.slice(2, 4), 16) || 0);
      cb.push(parseInt(h.slice(4, 6), 16) || 0);
      ca.push((parseInt(h.slice(6, 8), 16) || 0) / 255);
    }
    var k = colors.length;
    for (var p = 0; p < n; p++) {
      var r = data[p * 4], g = data[p * 4 + 1], b = data[p * 4 + 2], a = data[p * 4 + 3] / 255;
      var best = -1, bd = Infinity;
      for (var c = 0; c < k; c++) {
        var d;
        if (ca[c] < 0.5) {                       // 透明档：只跟"透明"比
          d = Math.abs(a - 0) * 255 * 4;
        } else if (a < 0.5) {                    // 图上透明，档不透明
          d = 255 * 4;
        } else {
          d = (r - cr[c]) * (r - cr[c]) + (g - cg[c]) * (g - cg[c]) + (b - cb[c]) * (b - cb[c]);
        }
        if (d < bd) { bd = d; best = c; }
      }
      out[p] = best < 0 ? 255 : best;
    }
    return out;
  }

  function compareToRef(refImg, bigImg, legend) {
    var c = document.createElement('canvas');
    c.width = REF_SIZE; c.height = REF_SIZE;
    var g = c.getContext('2d', { willReadFrequently: true });
    g.imageSmoothingEnabled = false;
    g.clearRect(0, 0, REF_SIZE, REF_SIZE);
    g.drawImage(bigImg, 0, 0, REF_SIZE, REF_SIZE);       // 1024 -> 256
    var a = classify(g.getImageData(0, 0, REF_SIZE, REF_SIZE).data, legend.colors);
    g.clearRect(0, 0, REF_SIZE, REF_SIZE);
    g.drawImage(refImg, 0, 0, REF_SIZE, REF_SIZE);       // 256 原生
    var b = classify(g.getImageData(0, 0, REF_SIZE, REF_SIZE).data, legend.colors);

    var total = REF_SIZE * REF_SIZE, same = 0, miss = 0;
    var bigEmpty = classifyEmptyIndex(legend.colors);
    for (var i = 0; i < total; i++) {
      if (a[i] === b[i]) same++; else if (b[i] !== bigEmpty) miss++;
    }
    return { agree: same / total, missing: miss / total };
  }

  function classifyEmptyIndex(colors) {
    for (var i = 0; i < colors.length; i++) {
      if (String(colors[i] || '').toUpperCase().slice(-2) === '00') return i;
    }
    return 255;
  }

  var _refCache = {};
  function setRef() {
    var f = frame(), box = $('refWrap'), im = $('refImg');
    var uri = (useWhite() && f.png256White) ? f.png256White : f.png256;
    if (!uri) { box.style.display = 'none'; return; }
    if (im.getAttribute('src') !== uri) im.setAttribute('src', uri);
    $('refDim').textContent = REF_SIZE + '×' + REF_SIZE;

    function compute() {
      var key = f.time + '|' + (uri === f.png256White ? 'w' : 'n');
      if (_refCache[key]) { show(_refCache[key]); return; }
      var big = new Image();
      big.onload = function () {
        try {
          var r = compareToRef(im, big, XT.legend);
          _refCache[key] = r; show(r);
        } catch (e) { show(null); }
      };
      big.onerror = function () { show(null); };
      big.src = currentPng(f);
    }
    function show(r) {
      if (!r) { $('refAgree').textContent = '—'; $('refMissing').textContent = '—'; return; }
      $('refAgree').textContent = (r.agree * 100).toFixed(2) + '%';
      $('refMissing').textContent = (r.missing * 100).toFixed(2) + '%';
    }
    if (im.complete && im.naturalWidth) compute();
    else im.onload = compute;
  }

  function setOverlay() {
    var f = frame();
    if (!map || !AMapNS) { setupFallbackImg(); return; }
    if (overlay) { map.remove(overlay); overlay = null; }
    var b = f.bbox;
    overlay = new AMapNS.ImageLayer({
      url: currentPng(f),
      bounds: new AMapNS.Bounds(new AMapNS.LngLat(b[0], b[1]), new AMapNS.LngLat(b[2], b[3])),
      zooms: [2, 20],
      opacity: Number($('ovOp').value) / 100,
      zIndex: Z_OVER
    });
    map.add(overlay);
    window.__over = overlay;                          // 调试引用
  }
  function fitToLayer() {
    var f = frame(); if (!map || !f) return;
    var b = f.bbox;
    map.setZoomAndCenter(fitZoom(b), [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2], false);
  }

  /* ---------------- 图例 ---------------- */
  function buildLegend() {
    var L = XT.legend, box = $('legend');
    var idx = L.breaks.map(function (_, i) { return i; });
    if (L.order !== 'asc') idx.reverse();
    idx.forEach(function (i) {
      var lo = L.breaks[i], hi = (i < L.breaks.length - 1) ? L.breaks[i + 1] : null;
      var rng = (i === L.breaks.length - 1) ? ('≥ ' + lo) : (lo + ' ~ ' + hi);
      var tr = String(L.colors[i] || '').toUpperCase().slice(-2) === '00';
      var row = document.createElement('div'); row.className = 'lg';
      var sw = document.createElement('span'); sw.className = 'sw' + (tr ? ' tr' : '');
      if (!tr) sw.style.background = L.colors[i];
      var a = document.createElement('span'); a.className = 'rng'; a.textContent = rng;
      var b = document.createElement('span'); b.className = 'txt';
      b.textContent = (L.labels[i] || '').replace(/^\s*[0-9.~≥]+\s*/, '');
      row.appendChild(sw); row.appendChild(a); row.appendChild(b);
      box.appendChild(row);
    });
  }

  /* ---------------- 绘制 ---------------- */
  function draw() {
    var f = frame();
    $('clock').textContent = f.label;
    $('dateStr').textContent = f.time.slice(0, 10) + '（' + XT.unit + '）';
    $('slider').value = cur;
    $('mGrid').textContent = f.cols + ' × ' + f.rows;
    $('mRange').textContent = f.vmin.toFixed(2) + ' ~ ' + f.vmax.toFixed(2) + ' ' + XT.unit;
    $('mMean').textContent = f.vmean.toFixed(3) + ' ' + XT.unit;
    $('mPoly').textContent = f.nPolygons;
    $('mDrawn').textContent = f.nDrawn;
    $('mBbox').textContent = f.bbox.map(function (v) { return v.toFixed(3); }).join(', ');
    $('hint').textContent = XT.title + ' · ' + f.time + ' · ' + f.cols + '×' + f.rows + ' 格网 · '
                          + f.nPolygons + ' 个等值面';
    setOverlay();
    setRef();
  }
  function go(i) { cur = Math.max(0, Math.min(XT.frames.length - 1, i)); draw(); }

  /* ---------------- 启动 ---------------- */
  $('title').textContent = (XT.title || '降水量') + ' · 地图视图';
  $('tagLayer').textContent = XT.layer + ' · ' + XT.title;
  $('tagEngine').textContent = XT.engine;
  $('tagSrc').textContent = XT.source;
  $('fSrc').textContent = XT.source;
  $('fEngine').textContent = XT.note || XT.engine;
  $('slider').max = XT.frames.length - 1;
  $('ticks').innerHTML = XT.frames.map(function (f) { return '<span>' + f.label + '</span>'; }).join('');
  if (!XT.frames.some(function (f) { return !!f.pngWhite; })) $('whiteWrap').style.display = 'none';
  buildLegend();

  $('slider').addEventListener('input', function () { go(+this.value); });
  $('prev').addEventListener('click', function () { go(cur - 1); });
  $('next').addEventListener('click', function () { go(cur + 1); });
  $('fit').addEventListener('click', fitToLayer);
  $('whiteChk').addEventListener('change', function () {
    $('whiteWrap').classList.toggle('on', this.checked); draw();
  });
  $('ovOp').addEventListener('input', function () {
    $('ovOpV').textContent = this.value + '%';
    if (overlay) overlay.setOpacity(Number(this.value) / 100);
  });
  $('baseOp').addEventListener('input', function () {
    $('baseOpV').textContent = this.value + '%';
    applyBase();
  });
  $('cbBase').addEventListener('change', function () {
    applyBase();
    this.parentNode.classList.toggle('on', this.checked);
  });
  $('cbOverlay').addEventListener('change', function () {
    if (overlay) this.checked ? overlay.show() : overlay.hide();
    this.parentNode.classList.toggle('on', this.checked);
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'ArrowLeft') go(cur - 1);
    if (e.key === 'ArrowRight') go(cur + 1);
  });
  window.addEventListener('resize', function () { if (!map) buildFallbackBase(); });

  /* 底图控制
     ---- 坑：AMap 2.0 里 `new AMap.Map({layers: []})` **并不会**去掉自带的底图，
     map.getLayers() 里仍然有内置的 NebulaLayer 与 LabelsLayer。如果再
     `AMap.createDefaultLayer()` 加一层，地图上就有两份底图，hide() 自己那份
     看起来"没反应"（其实关掉的是后面盖上去的那份，内置那层还在）。
     所以这里不加新层，直接控制地图上已有的、非 ImageLayer 的那些层。 */
  function baseLayersNow() {
    if (!map) return [];
    var ls = [];
    try { ls = map.getLayers() || []; } catch (e) { ls = []; }
    return ls.filter(function (l) {
      return String((l && l.CLASS_NAME) || '').indexOf('ImageLayer') < 0;
    });
  }
  function applyBase() {
    var on = $('cbBase').checked, op = Number($('baseOp').value) / 100;
    baseLayersNow().forEach(function (l) {
      try { if (l.setOpacity) l.setOpacity(op); } catch (e) {}
      try { on ? l.show() : l.hide(); } catch (e) {}
    });
  }

  function showFallback(msg) {
    var t = $('tagMap'); t.textContent = '底图不可用：' + msg; t.className = 'tag err';
    $('map').style.display = 'none';
    $('fallback').classList.add('on');
    buildFallbackBase();
  }
  function showMapOk() {
    var t = $('tagMap'); t.textContent = '高德底图 · 已就绪'; t.className = 'tag ok';
  }

  var f0 = frame();
  loadAmap().then(function (AMap) {
    AMapNS = AMap;
    var b = f0.bbox;
    map = new AMap.Map('map', {
      viewMode: '2D', zoom: fitZoom(b), center: [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2],
      layers: [], resizeEnable: true, showIndoorMap: false
    });
    applyBase();
    // 内置图层可能是异步加上去的，首帧渲染完成后再套一次
    if (map.on) map.on('complete', applyBase);
    window.__map = map;                              // 调试引用
    showMapOk();
    draw();
  }).catch(function (err) {
    console.error(err);
    showFallback(err.message || String(err));
    draw();
  });

  draw();   // 先把数据画上（此时可能还没地图，走兜底）
})();
