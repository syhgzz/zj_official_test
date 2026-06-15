export function createInterpolationOverlay(options) {
  const {
    map, data, colorFn,
    binaryRawData = null,
    algorithm = 'gaussian', baseSigma = 25, sigmaMultiplier = Infinity, maxRadius = 2000,
    debounceMs = 200, initDelayMs = 600, opacity = 0.7, gridStep = 2, baseZoom = 11,
    maxNearbyPoints = 0,
    idwPower = 2, idwEpsilon = 0.1,
    rbfType = 'thinPlate', rbfSmooth = 0,
    krigingModel = 'exponential', krigingNugget = 0, krigingRange = 200, krigingSill = 1,
    radiusJitter = false, mcSamples = 2, mcJitterFactor = 0.2,
    blurEnabled = false, blurRadius = 1.5,
    gpuEnabled = true,
    onRender = null
  } = options

  function hashLngLat(lng, lat, seed = 0) {
    let h = seed * 0x9e3779b9 + Math.floor(lng * 10000) * 73856093 ^ Math.floor(lat * 10000) * 19349663
    h = ((h >> 16) ^ h) * 0x45d9f3b; h = ((h >> 16) ^ h) * 0x45d9f3b; h = (h >> 16) ^ h
    return (h & 0x7fffffff) / 0x7fffffff
  }

  const container = map.getContainer()
  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  let imageLayer = null, visible = true, dirty = true, renderTimer = null, renderSeq = 0
  const blurCanvas = document.createElement('canvas')
  const blurCtx = blurCanvas.getContext('2d')

  // --- Worker setup ---
  let worker = null, workerReady = false, workerPending = false, useWorker = true
  let lastBounds = null, lastT0 = 0
  try {
    worker = new Worker(new URL('./interp-worker.js', import.meta.url), { type: 'module' })
    worker.onmessage = handleWorkerMessage
    worker.onerror = () => { useWorker = false; worker = null }
  } catch (e) { useWorker = false }

  // --- Color LUT cache (rebuild only when data/binaryRawData identity changes) ---
  let _cachedLUT = null, _cachedData = null, _cachedBinaryRawData = null

  function buildColorLUT() {
    if (_cachedData === data && _cachedBinaryRawData === binaryRawData && _cachedLUT) return _cachedLUT

    const lut = new Uint8Array(256 * 4)
    let vMin = Infinity, vMax = -Infinity
    // Use binaryRawData.val for value range when available (remote data paths)
    const brd = binaryRawData
    if (brd && brd.val && brd.val.length > 0) {
      for (let i = 0; i < brd.val.length; i++) { const v = brd.val[i]; if (v < vMin) vMin = v; if (v > vMax) vMax = v }
    } else {
      for (const d of data) { if (d.value < vMin) vMin = d.value; if (d.value > vMax) vMax = d.value }
    }
    if (!isFinite(vMin)) { vMin = -35; vMax = 25 }
    const range = vMax - vMin || 1
    for (let i = 0; i < 256; i++) {
      const v = vMin + range * i / 255
      const c = colorFn(v)
      lut[i * 4] = c[0]; lut[i * 4 + 1] = c[1]; lut[i * 4 + 2] = c[2]
      lut[i * 4 + 3] = c.length > 3 ? c[3] : 255
    }
    _cachedLUT = { lut, vMin, vMax }
    _cachedData = data
    _cachedBinaryRawData = binaryRawData
    return _cachedLUT
  }

  function handleWorkerMessage(e) {
    workerPending = false
    if (e.data._seq !== undefined && e.data._seq !== renderSeq) return
    if (e.data.type === 'done') {
      const tNow = performance.now()
      const url = URL.createObjectURL(e.data.blob)
      if (imageLayer) { imageLayer.setMap(null); URL.revokeObjectURL(imageLayer._blobUrl) }
      imageLayer = new AMap.ImageLayer({ url, bounds: lastBounds, opacity, zooms: [2, 20] })
      imageLayer._blobUrl = url
      if (visible) imageLayer.setMap(map)
      const tAfterLayer = performance.now()
      const workerTimings = e.data.timings || {}
      const mainTimings = e.data._mainTimings || {}
      const allTimings = {
        total: tNow - lastT0,
        ...mainTimings,
        ...workerTimings,
        main_imageLayer: tAfterLayer - tNow
      }
      if (onRender) onRender(allTimings)
      if (dirty) render()
    }
  }

  function getSigma(zoom) { return baseSigma * Math.pow(2, zoom - baseZoom) }
  function getRadius(sigma) { return Math.min(sigmaMultiplier * sigma, maxRadius) }

  function collectPixelPoints(radius, w, h) {
    const pts = []
    for (let i = 0; i < data.length; i++) {
      const pt = data[i], pixel = map.lngLatToContainer([pt.lng, pt.lat])
      if (pixel.x >= -radius && pixel.x <= w + radius && pixel.y >= -radius && pixel.y <= h + radius)
        pts.push({ x: pixel.x, y: pixel.y, value: pt.value })
    }
    return pts
  }

  function buildBins(pts, w, h, binSize) {
    const bCols = Math.ceil(w / binSize) + 1, bRows = Math.ceil(h / binSize) + 1
    const bins = Array.from({ length: bCols * bRows }, () => [])
    for (const p of pts) {
      const bc = Math.floor(p.x / binSize), br = Math.floor(p.y / binSize)
      if (bc >= 0 && bc < bCols && br >= 0 && br < bRows) bins[br * bCols + bc].push(p)
    }
    return { bins, bCols, bRows }
  }

  function queryBins(bins, bCols, bRows, bc, br, bRange, radius, sx, sy) {
    const results = []
    for (let dr = -bRange; dr <= bRange; dr++)
      for (let dc = -bRange; dc <= bRange; dc++) {
        const r = br + dr, c = bc + dc
        if (r < 0 || r >= bRows || c < 0 || c >= bCols) continue
        for (const p of bins[r * bCols + c]) {
          const dist2 = (sx - p.x) ** 2 + (sy - p.y) ** 2
          if (dist2 <= radius * radius) results.push({ ...p, dist2 })
        }
      }
    return results
  }

  function idwWeight(dist2, eps, power) { return 1 / Math.pow(dist2 + eps, power / 2) }

  function rbfPhi(r2, type) {
    if (type === 'thinPlate') { const r = Math.sqrt(r2); return r < 1e-9 ? 0 : r2 * Math.log(r + 1e-9) }
    if (type === 'multiquadric') return Math.sqrt(r2 + 1)
    if (type === 'gaussian') return Math.exp(-r2)
    return r2 * Math.log(Math.sqrt(r2) + 1e-9)
  }

  function solveLinear(A, b, n) {
    for (let i = 0; i < n; i++) {
      let max = i
      for (let j = i + 1; j < n; j++) if (Math.abs(A[j][i]) > Math.abs(A[max][i])) max = j
      if (i !== max) { const ta = A[i]; A[i] = A[max]; A[max] = ta; const tb = b[i]; b[i] = b[max]; b[max] = tb }
      if (Math.abs(A[i][i]) < 1e-12) continue
      for (let j = i + 1; j < n; j++) {
        const f = A[j][i] / A[i][i]
        for (let k = i; k < n; k++) A[j][k] -= f * A[i][k]
        b[j] -= f * b[i]
      }
    }
    const x = new Float64Array(n)
    for (let i = n - 1; i >= 0; i--) {
      let s = b[i]
      for (let j = i + 1; j < n; j++) s -= A[i][j] * x[j]
      x[i] = Math.abs(A[i][i]) > 1e-12 ? s / A[i][i] : 0
    }
    return x
  }

  function computeRBFWeights(localPts, type, smooth) {
    const n = localPts.length
    const A = new Array(n).fill(0).map(() => new Float64Array(n))
    const b = new Float64Array(n)
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        const d2 = (localPts[i].x - localPts[j].x) ** 2 + (localPts[i].y - localPts[j].y) ** 2
        A[i][j] = rbfPhi(d2, type) + (i === j ? smooth : 0)
      }
      b[i] = localPts[i].value
    }
    return { weights: solveLinear(A, b, n), points: localPts }
  }

  function rbfValue(sx, sy, rbfR, type) {
    let v = 0
    for (let i = 0; i < rbfR.points.length; i++) {
      const d2 = (sx - rbfR.points[i].x) ** 2 + (sy - rbfR.points[i].y) ** 2
      v += rbfR.weights[i] * rbfPhi(d2, type)
    }
    return v
  }

  function variogram(h, model, nugget, range, sill) {
    if (h < 1e-9) return nugget
    const psill = sill - nugget
    if (model === 'exponential') return nugget + psill * (1 - Math.exp(-3 * h / range))
    if (model === 'spherical') { const r = h / range; return nugget + psill * (r < 1 ? 1.5 * r - 0.5 * r * r * r : 1) }
    if (model === 'gaussian') return nugget + psill * (1 - Math.exp(-3 * h * h / (range * range)))
    return nugget + psill * (1 - Math.exp(-3 * h / range))
  }

  function computeKrigingWeights(localPts, model, nugget, range, sill) {
    const n = localPts.length, N = n + 1
    const A = new Array(N).fill(0).map(() => new Float64Array(N))
    const b = new Float64Array(N)
    for (let i = 0; i < n; i++) {
      for (let j = 0; j <= i; j++) {
        const d = Math.sqrt((localPts[i].x - localPts[j].x) ** 2 + (localPts[i].y - localPts[j].y) ** 2)
        A[i][j] = A[j][i] = variogram(d, model, nugget, range, sill)
      }
      A[i][n] = A[n][i] = 1; b[i] = localPts[i].value
    }
    A[n][n] = 0; b[n] = 0
    return { weights: solveLinear(A, b, N), points: localPts, n }
  }

  function krigingValue(sx, sy, kr, model, nugget, range, sill) {
    let v = 0
    for (let i = 0; i < kr.n; i++) {
      const d = Math.sqrt((sx - kr.points[i].x) ** 2 + (sy - kr.points[i].y) ** 2)
      v += kr.weights[i] * variogram(d, model, nugget, range, sill)
    }
    return v + kr.weights[kr.n]
  }

  function computeCellValue(x, y, sigma, radius, bc, br, bins, bCols, bRows, bRange) {
    let nearby = queryBins(bins, bCols, bRows, bc, br, bRange, radius, x, y)
    if (!nearby.length) return null
    if (algorithm === 'gaussian') {
      const nh = -0.5 / (sigma * sigma); let sW = 0, sV = 0
      const limit = maxNearbyPoints > 0 ? Math.min(maxNearbyPoints, nearby.length) : nearby.length
      const nby = limit < nearby.length ? nearby.sort((a, b) => a.dist2 - b.dist2).slice(0, limit) : nearby
      for (const p of nby) { const w = Math.exp(p.dist2 * nh); sW += w; sV += w * p.value }
      return sW > 0 ? sV / sW : null
    }
    if (algorithm === 'idw') {
      let sW = 0, sV = 0
      const limit = maxNearbyPoints > 0 ? Math.min(maxNearbyPoints, nearby.length) : nearby.length
      const nby = limit < nearby.length ? nearby.sort((a, b) => a.dist2 - b.dist2).slice(0, limit) : nearby
      for (const p of nby) { const w = idwWeight(p.dist2, idwEpsilon, idwPower); sW += w; sV += w * p.value }
      return sW > 0 ? sV / sW : null
    }
    if (algorithm === 'rbf') {
      if (nearby.length < 3) return null
      const limit = maxNearbyPoints > 0 ? Math.min(maxNearbyPoints, nearby.length) : 80
      const rbfR = computeRBFWeights(nearby.slice(0, limit), rbfType, rbfSmooth)
      return rbfValue(x, y, rbfR, rbfType)
    }
    if (algorithm === 'kriging') {
      if (nearby.length < 3) return null
      const limit = maxNearbyPoints > 0 ? Math.min(maxNearbyPoints, nearby.length) : 60
      const kr = computeKrigingWeights(nearby.slice(0, limit), krigingModel, krigingNugget, krigingRange, krigingSill)
      return krigingValue(x, y, kr, krigingModel, krigingNugget, krigingRange, krigingSill)
    }
    return null
  }

  function hasData() {
    return data.length > 0 || (binaryRawData && binaryRawData.lng && binaryRawData.lng.length > 0)
  }

  function getDataCount() {
    if (binaryRawData && binaryRawData.lng) return binaryRawData.lng.length
    return data.length
  }

  function render() {
    if (!visible || !dirty || !hasData()) return
    if (workerPending) return
    dirty = false
    const tStart = performance.now()
    const zoom = map.getZoom(), sigma = getSigma(zoom)
    const baseR = getRadius(sigma)
    const maxJitterR = radiusJitter && mcSamples >= 1 ? baseR * 1.5 : baseR
    const w = container.clientWidth, h = container.clientHeight
    if (!w || !h) return
    lastBounds = map.getBounds()

    const tCollect0 = performance.now()
    const useGPU = worker && gpuEnabled && (algorithm === 'idw' || algorithm === 'gaussian') && !radiusJitter
    // For GPU path, we send raw lng/lat/val to worker - no need for pixelPoints
    // For CPU path, collect pixelPoints from data (binaryRawData case uses GPU)
    const pixelPoints = useGPU ? [] : collectPixelPoints(maxJitterR, w, h)
    const tCollect1 = performance.now()
    lastT0 = tStart
    if (!pixelPoints.length && !hasData()) return

    if (worker) {
      workerPending = true
      const tLut0 = performance.now()
      const { lut, vMin, vMax } = buildColorLUT()
      const tLut1 = performance.now()
      const sw = lastBounds.getSouthWest(), ne = lastBounds.getNorthEast()
      const seq = ++renderSeq
      const msg = {
        type: 'render',
        _seq: seq,
        bounds: { swLng: sw.lng, swLat: sw.lat, neLng: ne.lng, neLat: ne.lat },
        // pixel coords for CPU fallback
        pixelPoints, w, h, sigma, baseR, maxJitterR,
        gridStep, opacity, algorithm, idwPower, idwEpsilon,
        rbfType, rbfSmooth, krigingModel, krigingNugget,
        krigingRange, krigingSill, radiusJitter, mcSamples,
        mcJitterFactor, blurEnabled, blurRadius,
        gpuEnabled, maxNearbyPoints,
        colorLut: lut, valueMin: vMin, valueMax: vMax,
        _mainTimings: {
          main_collectPoints: tCollect1 - tCollect0,
          main_buildLUT: tLut1 - tLut0,
          main_postMessage: performance.now() - tLut1
        }
      }
      // Use binaryRawData arrays when available (copy via slice since
      // the originals may be re-used across renders and must not be detached)
      const brd = binaryRawData
      if (brd && brd.lng && brd.val) {
        const copyLng = brd.lng.slice()
        const copyLat = brd.lat.slice()
        const copyVal = brd.val.slice()
        msg.rawLng = copyLng
        msg.rawLat = copyLat
        msg.rawVal = copyVal
        worker.postMessage(msg, [copyLng.buffer, copyLat.buffer, copyVal.buffer])
      } else {
        const n = data.length
        const rawLng = new Float32Array(n)
        const rawLat = new Float32Array(n)
        const rawVal = new Float32Array(n)
        for (let i = 0; i < n; i++) {
          rawLng[i] = data[i].lng
          rawLat[i] = data[i].lat
          rawVal[i] = data[i].value
        }
        msg.rawLng = rawLng
        msg.rawLat = rawLat
        msg.rawVal = rawVal
        worker.postMessage(msg, [rawLng.buffer, rawLat.buffer, rawVal.buffer])
      }
      return
    }

    // CPU fallback
    canvas.width = w; canvas.height = h
    ctx.clearRect(0, 0, w, h)
    const isInfR = !isFinite(maxJitterR)
    const binSize = isInfR ? Math.max(w, h) : Math.ceil(maxJitterR)
    const { bins, bCols, bRows } = buildBins(pixelPoints, w, h, binSize)
    const bRange = isInfR ? 1 : Math.ceil(maxJitterR / binSize)

    for (let y = 0; y < h; y += gridStep) {
      for (let x = 0; x < w; x += gridStep) {
        const bc = Math.floor(x / binSize), br = Math.floor(y / binSize)
        let sumMC = 0, countMC = 0
        if (radiusJitter && mcSamples >= 1) {
          for (let s = 0; s < mcSamples; s++) {
            const r = s === 0 ? baseR : baseR * (1 + hashLngLat(x, y, s) * mcJitterFactor)
            const val = computeCellValue(x, y, sigma, r, bc, br, bins, bCols, bRows, bRange)
            if (val !== null) { sumMC += val; countMC++ }
          }
        } else {
          const val = computeCellValue(x, y, sigma, baseR, bc, br, bins, bCols, bRows, bRange)
          if (val !== null) { sumMC = val; countMC = 1 }
        }
        if (countMC > 0) {
          const c = colorFn(sumMC / countMC)
          const a = (c.length > 3 ? c[3] : 255) / 255
          ctx.fillStyle = `rgba(${c[0]},${c[1]},${c[2]},${(a * opacity).toFixed(3)})`
          ctx.fillRect(x, y, gridStep, gridStep)
        }
      }
    }
    const outputCanvas = blurEnabled && blurRadius > 0 ? blurCanvas : canvas
    if (blurEnabled && blurRadius > 0) {
      blurCanvas.width = w; blurCanvas.height = h
      blurCtx.filter = `blur(${blurRadius}px)`
      blurCtx.drawImage(canvas, 0, 0)
      blurCtx.filter = 'none'
    }
    const bounds = lastBounds
    const seq = ++renderSeq
    const prevLayer = imageLayer
    outputCanvas.toBlob(blob => {
      if (seq !== renderSeq) return
      const url = URL.createObjectURL(blob)
      if (prevLayer) { prevLayer.setMap(null); URL.revokeObjectURL(prevLayer._blobUrl) }
      imageLayer = new AMap.ImageLayer({ url, bounds, opacity, zooms: [2, 20] })
      imageLayer._blobUrl = url
      if (visible) imageLayer.setMap(map)
      if (onRender) onRender(performance.now() - lastT0)
    }, 'image/png')
  }

  function scheduleRender() { dirty = true; clearTimeout(renderTimer); renderTimer = setTimeout(render, debounceMs) }
  map.on('zoomend', scheduleRender); map.on('moveend', scheduleRender)
  setTimeout(() => { dirty = true; render() }, initDelayMs)
  return {
    show() { visible = true; if (imageLayer) imageLayer.setMap(map); dirty = true; render() },
    hide() { visible = false; if (imageLayer) imageLayer.setMap(null) },
    destroy() { visible = false; if (imageLayer) { imageLayer.setMap(null); imageLayer = null } if (worker) { worker.terminate(); worker = null } map.off('zoomend', scheduleRender); map.off('moveend', scheduleRender); clearTimeout(renderTimer) }
  }
}
