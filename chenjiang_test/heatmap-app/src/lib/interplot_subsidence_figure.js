export function createInterpolationOverlay(options) {
  const {
    map, data, colorFn,
    algorithm = 'gaussian', baseSigma = 25, sigmaMultiplier = 3, maxRadius = 2000,
    debounceMs = 200, initDelayMs = 600, opacity = 0.7, gridStep = 4, baseZoom = 11,
    idwPower = 2, idwEpsilon = 0.1,
    rbfType = 'thinPlate', rbfSmooth = 0,
    krigingModel = 'exponential', krigingNugget = 0, krigingRange = 200, krigingSill = 1
  } = options

  const container = map.getContainer()
  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  let imageLayer = null, visible = true, dirty = true, renderTimer = null

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

  function render() {
    if (!visible || !dirty || !data.length) return
    dirty = false
    const zoom = map.getZoom(), sigma = getSigma(zoom), radius = getRadius(sigma)
    const binSize = Math.ceil(radius)
    const w = container.clientWidth, h = container.clientHeight
    if (!w || !h) return
    canvas.width = w; canvas.height = h

    const pixelPoints = collectPixelPoints(radius, w, h)
    if (!pixelPoints.length) return

    const { bins, bCols, bRows } = buildBins(pixelPoints, w, h, binSize)
    const imageData = ctx.createImageData(w, h), d = imageData.data
    const bRange = Math.ceil(radius / binSize)
    const RBF_MAX = 80, KRIGING_MAX = 60

    for (let y = 0; y < h; y += gridStep) {
      for (let x = 0; x < w; x += gridStep) {
        const bc = Math.floor(x / binSize), br = Math.floor(y / binSize)
        let result = null

        if (algorithm === 'gaussian' || algorithm === 'idw') {
          const nearby = queryBins(bins, bCols, bRows, bc, br, bRange, radius, x, y)
          if (!nearby.length) continue
          let sumW = 0, sumV = 0
          if (algorithm === 'gaussian') {
            const nh = -0.5 / (sigma * sigma)
            for (const p of nearby) { const w = Math.exp(p.dist2 * nh); sumW += w; sumV += w * p.value }
          } else {
            for (const p of nearby) { const w = idwWeight(p.dist2, idwEpsilon, idwPower); sumW += w; sumV += w * p.value }
          }
          if (sumW > 0) result = sumV / sumW
        } else if (algorithm === 'rbf') {
          const nearby = queryBins(bins, bCols, bRows, bc, br, bRange, radius, x, y)
          if (nearby.length < 3) continue
          const local = nearby.slice(0, RBF_MAX)
          const rbfR = computeRBFWeights(local, rbfType, rbfSmooth)
          result = rbfValue(x, y, rbfR, rbfType)
        } else if (algorithm === 'kriging') {
          const nearby = queryBins(bins, bCols, bRows, bc, br, bRange, radius, x, y)
          if (nearby.length < 3) continue
          const local = nearby.slice(0, KRIGING_MAX)
          const kr = computeKrigingWeights(local, krigingModel, krigingNugget, krigingRange, krigingSill)
          result = krigingValue(x, y, kr, krigingModel, krigingNugget, krigingRange, krigingSill)
        }

        if (result !== null) {
          const [cr, cg, cb] = colorFn(result)
          const alpha = Math.floor(opacity * 255)
          const maxY = Math.min(y + gridStep, h), maxX = Math.min(x + gridStep, w)
          for (let dy = y; dy < maxY; dy++)
            for (let dx = x; dx < maxX; dx++) {
              const idx = (dy * w + dx) * 4
              d[idx] = cr; d[idx + 1] = cg; d[idx + 2] = cb; d[idx + 3] = alpha
            }
        }
      }
    }
    ctx.putImageData(imageData, 0, 0)
    const bounds = map.getBounds()
    if (imageLayer) imageLayer.setMap(null)
    imageLayer = new AMap.ImageLayer({ url: canvas.toDataURL('image/png'), bounds, opacity, zooms: [2, 20] })
    if (visible) imageLayer.setMap(map)
  }

  function scheduleRender() { dirty = true; clearTimeout(renderTimer); renderTimer = setTimeout(render, debounceMs) }
  map.on('zoomend', scheduleRender); map.on('moveend', scheduleRender)
  setTimeout(() => { dirty = true; render() }, initDelayMs)
  return {
    show() { visible = true; if (imageLayer) imageLayer.setMap(map); dirty = true; render() },
    hide() { visible = false; if (imageLayer) imageLayer.setMap(null) },
    destroy() { visible = false; if (imageLayer) { imageLayer.setMap(null); imageLayer = null } map.off('zoomend', scheduleRender); map.off('moveend', scheduleRender); clearTimeout(renderTimer) }
  }
}
