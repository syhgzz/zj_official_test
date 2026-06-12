export function createInterpolationOverlay(options) {
  const { map, data, colorFn, baseSigma = 25, sigmaMultiplier = 3, maxRadius = 300, debounceMs = 200, initDelayMs = 600, opacity = 0.7, gridStep = 4, baseZoom = 11 } = options
  const container = map.getContainer()
  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  let imageLayer = null, visible = true, dirty = true, renderTimer = null

  function render() {
    if (!visible || !dirty || !data.length) return
    dirty = false
    const zoom = map.getZoom()
    const sigma = baseSigma * Math.pow(2, zoom - baseZoom)
    const radius = Math.min(sigmaMultiplier * sigma, maxRadius)
    const binSize = Math.ceil(radius)
    const w = container.clientWidth, h = container.clientHeight
    if (!w || !h) return
    canvas.width = w; canvas.height = h

    const pixelPoints = []
    for (let i = 0; i < data.length; i++) {
      const pt = data[i], pixel = map.lngLatToContainer([pt.lng, pt.lat])
      if (pixel.x >= -radius && pixel.x <= w + radius && pixel.y >= -radius && pixel.y <= h + radius)
        pixelPoints.push({ x: pixel.x, y: pixel.y, value: pt.value })
    }
    if (!pixelPoints.length) return

    const bCols = Math.ceil(w / binSize) + 1, bRows = Math.ceil(h / binSize) + 1
    const bins = Array.from({ length: bCols * bRows }, () => [])
    for (let i = 0; i < pixelPoints.length; i++) {
      const p = pixelPoints[i], bc = Math.floor(p.x / binSize), br = Math.floor(p.y / binSize)
      if (bc >= 0 && bc < bCols && br >= 0 && br < bRows) bins[br * bCols + bc].push(p)
    }

    const imageData = ctx.createImageData(w, h), d = imageData.data
    const bRange = Math.ceil(radius / binSize), negHalfSigma2 = -0.5 / (sigma * sigma)
    for (let y = 0; y < h; y += gridStep) {
      for (let x = 0; x < w; x += gridStep) {
        const bc = Math.floor(x / binSize), br = Math.floor(y / binSize)
        let sumW = 0, sumV = 0
        for (let dr = -bRange; dr <= bRange; dr++)
          for (let dc = -bRange; dc <= bRange; dc++) {
            const r = br + dr, c = bc + dc
            if (r < 0 || r >= bRows || c < 0 || c >= bCols) continue
            for (const p of bins[r * bCols + c]) {
              const dx = x - p.x, dy = y - p.y, dist2 = dx * dx + dy * dy
              if (dist2 > radius * radius) continue
              const w = Math.exp(dist2 * negHalfSigma2); sumW += w; sumV += w * p.value
            }
          }
        if (sumW > 0) {
          const [cr, cg, cb] = colorFn(sumV / sumW), alpha = Math.floor(opacity * 255)
          const maxY = Math.min(y + gridStep, h), maxX = Math.min(x + gridStep, w)
          for (let dy = y; dy < maxY; dy++)
            for (let dx = x; dx < maxX; dx++) { const idx = (dy * w + dx) * 4; d[idx] = cr; d[idx + 1] = cg; d[idx + 2] = cb; d[idx + 3] = alpha }
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
