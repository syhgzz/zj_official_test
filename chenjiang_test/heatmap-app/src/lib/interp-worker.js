// interp-worker.js — OffscreenCanvas interpolation renderer

import { splatRender } from './webgl-splat.js'

function hashLngLat(lng, lat, seed = 0) {
  let h = seed * 0x9e3779b9 + Math.floor(lng * 10000) * 73856093 ^ Math.floor(lat * 10000) * 19349663
  h = ((h >> 16) ^ h) * 0x45d9f3b; h = ((h >> 16) ^ h) * 0x45d9f3b; h = (h >> 16) ^ h
  return (h & 0x7fffffff) / 0x7fffffff
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

function variogram(h, model, nugget, range, sill) {
  if (h < 1e-9) return nugget
  const psill = sill - nugget
  if (model === 'exponential') return nugget + psill * (1 - Math.exp(-3 * h / range))
  if (model === 'spherical') { const r = h / range; return nugget + psill * (r < 1 ? 1.5 * r - 0.5 * r * r * r : 1) }
  if (model === 'gaussian') return nugget + psill * (1 - Math.exp(-3 * h * h / (range * range)))
  return nugget + psill * (1 - Math.exp(-3 * h / range))
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

function computeCellValue(x, y, sigma, radius, bc, br, bins, bCols, bRows, bRange, algo, idwPower, idwEpsilon, rbfType, rbfSmooth, krigingModel, krigingNugget, krigingRange, krigingSill) {
  const nearby = queryBins(bins, bCols, bRows, bc, br, bRange, radius, x, y)
  if (!nearby.length) return null
  if (algo === 'gaussian') {
    const nh = -0.5 / (sigma * sigma); let sW = 0, sV = 0
    for (const p of nearby) { const w = Math.exp(p.dist2 * nh); sW += w; sV += w * p.value }
    return sW > 0 ? sV / sW : null
  }
  if (algo === 'idw') {
    let sW = 0, sV = 0
    for (const p of nearby) { const w = idwWeight(p.dist2, idwEpsilon, idwPower); sW += w; sV += w * p.value }
    return sW > 0 ? sV / sW : null
  }
  if (algo === 'rbf') {
    if (nearby.length < 3) return null
    const rbfR = computeRBFWeights(nearby.slice(0, 80), rbfType, rbfSmooth)
    return rbfValue(x, y, rbfR, rbfType)
  }
  if (algo === 'kriging') {
    if (nearby.length < 3) return null
    const kr = computeKrigingWeights(nearby.slice(0, 60), krigingModel, krigingNugget, krigingRange, krigingSill)
    return krigingValue(x, y, kr, krigingModel, krigingNugget, krigingRange, krigingSill)
  }
  return null
}

function lookupColor(v, lut, vMin, vMax) {
  const t = (v - vMin) / (vMax - vMin)
  const idx = Math.max(0, Math.min(255, Math.floor(t * 255)))
  const off = idx * 3
  return [lut[off], lut[off + 1], lut[off + 2]]
}

let offscreen = null, ctx = null, blurCanvas = null, blurCtx = null

self.onmessage = function (e) {
  const msg = e.data
  if (msg.type === 'render') {
    const {
      pixelPoints, w, h, sigma, baseR, maxJitterR, gridStep,
      opacity, algorithm, idwPower, idwEpsilon, rbfType, rbfSmooth,
      krigingModel, krigingNugget, krigingRange, krigingSill,
      radiusJitter, mcSamples, mcJitterFactor,
      blurEnabled, blurRadius, gpuEnabled,
      colorLut, valueMin, valueMax
    } = msg

    if (!offscreen || offscreen.width !== w || offscreen.height !== h) {
      offscreen = new OffscreenCanvas(w, h)
      ctx = offscreen.getContext('2d')
      blurCanvas = new OffscreenCanvas(w, h)
      blurCtx = blurCanvas.getContext('2d')
    }

    ctx.clearRect(0, 0, w, h)

    if (!pixelPoints.length) {
      offscreen.convertToBlob({ type: 'image/png' }).then(blob => {
        self.postMessage({ type: 'done', blob })
      })
      return
    }

    // GPU IDW splatting (no jitter, gpu enabled)
    if (gpuEnabled && algorithm === 'idw' && !radiusJitter && splatRender) {
      try {
        const pixels = splatRender(pixelPoints, { w, h, radius: baseR, idwPower, idwEpsilon, opacity, colorLut, valueMin, valueMax, gridStep })
        if (pixels) {
          const imgData = ctx.createImageData(w, h)
          imgData.data.set(pixels)
          ctx.putImageData(imgData, 0, 0)
          if (blurEnabled && blurRadius > 0) {
            blurCanvas.width = w; blurCanvas.height = h
            blurCtx.filter = `blur(${blurRadius}px)`
            blurCtx.drawImage(offscreen, 0, 0)
            blurCtx.filter = 'none'
          }
          (blurEnabled && blurRadius > 0 ? blurCanvas : offscreen).convertToBlob({ type: 'image/png' }).then(blob => {
            self.postMessage({ type: 'done', blob })
          })
          return
        }
      } catch (e) { /* CPU fallback */ }
    }

    const binSize = Math.ceil(maxJitterR)
    const { bins, bCols, bRows } = buildBins(pixelPoints, w, h, binSize)
    const bRange = Math.ceil(maxJitterR / binSize)

      for (let y = 0; y < h; y += gridStep) {
      for (let x = 0; x < w; x += gridStep) {
        const bc = Math.floor(x / binSize), br = Math.floor(y / binSize)
        let sumMC = 0, countMC = 0

        if (radiusJitter && mcSamples >= 1) {
          for (let s = 0; s < mcSamples; s++) {
            const r = s === 0 ? baseR : baseR * (1 + hashLngLat(x, y, s) * mcJitterFactor)
            const val = computeCellValue(x, y, sigma, r, bc, br, bins, bCols, bRows, bRange,
              algorithm, idwPower, idwEpsilon, rbfType, rbfSmooth,
              krigingModel, krigingNugget, krigingRange, krigingSill)
            if (val !== null) { sumMC += val; countMC++ }
          }
        } else {
          const val = computeCellValue(x, y, sigma, baseR, bc, br, bins, bCols, bRows, bRange,
            algorithm, idwPower, idwEpsilon, rbfType, rbfSmooth,
            krigingModel, krigingNugget, krigingRange, krigingSill)
          if (val !== null) { sumMC = val; countMC = 1 }
        }

        if (countMC > 0) {
          const [cr, cg, cb] = lookupColor(sumMC / countMC, colorLut, valueMin, valueMax)
          ctx.fillStyle = `rgba(${cr},${cg},${cb},${opacity})`
          ctx.fillRect(x, y, gridStep, gridStep)
        }
      }
    }

    const outputCanvas = blurEnabled && blurRadius > 0 ? blurCanvas : offscreen
    if (blurEnabled && blurRadius > 0) {
      blurCanvas.width = w; blurCanvas.height = h
      blurCtx.filter = `blur(${blurRadius}px)`
      blurCtx.drawImage(offscreen, 0, 0)
      blurCtx.filter = 'none'
    }

    outputCanvas.convertToBlob({ type: 'image/png' }).then(blob => {
      self.postMessage({ type: 'done', blob })
    })
  }
}
